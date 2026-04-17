from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .converter import detect_and_convert
from .models import Lecture, LectureSegment
from .serializers import (
    BulkImportSerializer,
    LectureListSerializer,
    LectureSegmentSerializer,
    LectureSerializer,
)
from .tasks import index_lecture_segments


class LectureListCreateView(generics.ListCreateAPIView):
    queryset = Lecture.objects.prefetch_related("segments").all()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return LectureListSerializer
        return LectureSerializer


class LectureDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Lecture.objects.prefetch_related("segments").all()
    serializer_class = LectureSerializer


class LectureSegmentListView(generics.ListAPIView):
    serializer_class = LectureSegmentSerializer

    def get_queryset(self):
        return LectureSegment.objects.filter(lecture_id=self.kwargs["lecture_pk"])


class BulkImportView(APIView):
    """
    STT 데이터 일괄 임포트 + FAISS 인덱싱 트리거

    지원 형식:
    1. 내부 형식: {"title", "source_file", "segments": [{"start_time", "end_time", "transcript"}]}
    2. 외부 형식: {"slides_data": [...], "materials": [...]}  (자동 변환)
    """

    def post(self, request):
        data = request.data

        # 외부 형식 자동 감지 → 내부 형식으로 변환
        converted = detect_and_convert(data)

        if converted:
            return self._import_multiple(converted)

        # 내부 형식 그대로 처리
        return self._import_single(data)

    def _import_single(self, data):
        serializer = BulkImportSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        lecture = Lecture.objects.create(
            title=vd["title"],
            source_file=vd["source_file"],
            description=vd.get("description", ""),
        )

        segments = [
            LectureSegment(
                lecture=lecture,
                start_time=seg["start_time"],
                end_time=seg["end_time"],
                transcript=seg["transcript"],
            )
            for seg in vd["segments"]
        ]
        LectureSegment.objects.bulk_create(segments)

        task = index_lecture_segments.delay(lecture.id)

        return Response(
            {
                "lecture_id": lecture.id,
                "segments_count": len(segments),
                "indexing_task_id": task.id,
                "message": "강의 데이터가 저장되었으며, 벡터 인덱싱이 시작되었습니다.",
            },
            status=status.HTTP_201_CREATED,
        )

    def _import_multiple(self, converted_list):
        results = []
        for item in converted_list:
            serializer = BulkImportSerializer(data=item)
            if not serializer.is_valid():
                results.append({
                    "source_file": item.get("source_file", "?"),
                    "status": "error",
                    "errors": serializer.errors,
                })
                continue

            vd = serializer.validated_data
            lecture = Lecture.objects.create(
                title=vd["title"],
                source_file=vd["source_file"],
                description=vd.get("description", ""),
            )

            segments = [
                LectureSegment(
                    lecture=lecture,
                    start_time=seg["start_time"],
                    end_time=seg["end_time"],
                    transcript=seg["transcript"],
                )
                for seg in vd["segments"]
            ]
            LectureSegment.objects.bulk_create(segments)

            task = index_lecture_segments.delay(lecture.id)
            results.append({
                "lecture_id": lecture.id,
                "title": vd["title"],
                "source_file": vd["source_file"],
                "segments_count": len(segments),
                "indexing_task_id": task.id,
                "status": "created",
            })

        total = len(results)
        success = sum(1 for r in results if r.get("status") == "created")

        return Response(
            {
                "total": total,
                "success": success,
                "failed": total - success,
                "results": results,
                "message": f"{success}개 강의가 저장되었으며, 벡터 인덱싱이 시작되었습니다.",
            },
            status=status.HTTP_201_CREATED,
        )
