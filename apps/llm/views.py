from celery.result import AsyncResult
from django.conf import settings
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LLMQuery, QueryStatus
from .serializers import LLMQueryCreateSerializer, LLMQueryResultSerializer
from .tasks import clip_video_segments, merge_video_clips, process_llm_query


class LLMQueryView(APIView):
    """LLM 쿼리 생성 (비동기 처리)"""

    def post(self, request):
        serializer = LLMQueryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        query = LLMQuery.objects.create(
            query_text=data["query_text"],
            query_type=data["query_type"],
            model_name=data["model_name"],
        )

        task = process_llm_query.delay(
            query_id=query.id,
            lecture_id=data.get("lecture_id"),
        )

        query.task_id = task.id
        query.save(update_fields=["task_id"])

        return Response(
            {
                "query_id": query.id,
                "task_id": task.id,
                "status": "pending",
                "message": "쿼리가 접수되었습니다. task_id로 결과를 조회하세요.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class LLMQueryDetailView(generics.RetrieveAPIView):
    """쿼리 결과 조회"""

    queryset = LLMQuery.objects.all()
    serializer_class = LLMQueryResultSerializer


class TaskStatusView(APIView):
    """Celery 태스크 상태 확인"""

    def get(self, request, task_id):
        result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": result.status,
        }

        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            else:
                response_data["error"] = str(result.result)

        query = LLMQuery.objects.filter(task_id=task_id).first()
        if query:
            response_data["query_id"] = query.id
            response_data["query_status"] = query.status
            if query.status == "completed":
                response_data["result_text"] = query.result_text
                response_data["retrieved_segments"] = query.retrieved_segments

        return Response(response_data)


class AvailableModelsView(APIView):
    """사용 가능한 LLM 모델 목록"""

    def get(self, request):
        models = {
            key: {"model_id": value, "key": key}
            for key, value in settings.OLLAMA_MODELS.items()
        }
        return Response(
            {
                "models": models,
                "default": settings.OLLAMA_DEFAULT_MODEL,
            }
        )


class LLMQueryListView(generics.ListAPIView):
    """쿼리 이력 조회"""

    queryset = LLMQuery.objects.all()
    serializer_class = LLMQueryResultSerializer


class ClipVideoView(APIView):
    """인용된 영상 구간을 ffmpeg으로 클리핑 (수동 트리거)"""

    def post(self, request, pk):
        try:
            query = LLMQuery.objects.get(pk=pk)
        except LLMQuery.DoesNotExist:
            return Response({"error": "쿼리를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        if query.status != QueryStatus.COMPLETED:
            return Response(
                {"error": "RAG 쿼리가 완료된 후에만 클립을 생성할 수 있습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cited_sources = [s for s in (query.retrieved_segments or []) if s.get("cited")]
        if not cited_sources:
            return Response({"error": "인용된 출처가 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.llm.services.video_clip_service import ASPECT_RATIO_PRESETS
        aspect_ratio   = request.data.get("aspect_ratio") or None
        with_subtitles = bool(request.data.get("with_subtitles", True))

        if aspect_ratio and aspect_ratio not in ASPECT_RATIO_PRESETS:
            return Response(
                {"error": f"지원하지 않는 비율입니다. 사용 가능: {list(ASPECT_RATIO_PRESETS)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query.video_clips = []
        query.save(update_fields=["video_clips"])

        task = clip_video_segments.delay(
            query.id, cited_sources,
            aspect_ratio=aspect_ratio,
            with_subtitles=with_subtitles,
        )

        return Response(
            {"message": "클립 생성이 시작되었습니다.", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )


class MergeVideoView(APIView):
    """성공한 클립들을 하나의 mp4로 머지 (수동 트리거)"""

    def post(self, request, pk):
        try:
            query = LLMQuery.objects.get(pk=pk)
        except LLMQuery.DoesNotExist:
            return Response({"error": "쿼리를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        success_clips = [c for c in (query.video_clips or []) if c.get("status") == "success"]
        if not success_clips:
            return Response(
                {"error": "머지할 성공한 클립이 없습니다. 먼저 클립 자르기를 실행하세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query.merged_clip = {}
        query.save(update_fields=["merged_clip"])

        task = merge_video_clips.delay(query.id)

        return Response(
            {"message": "머지가 시작되었습니다.", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED,
        )
