from rest_framework import serializers

from .models import Lecture, LectureSegment


class LectureSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LectureSegment
        fields = [
            "id",
            "start_time",
            "end_time",
            "transcript",
            "time_range",
            "created_at",
        ]
        read_only_fields = ["id", "time_range", "created_at"]


class LectureSerializer(serializers.ModelSerializer):
    segments = LectureSegmentSerializer(many=True, read_only=True)
    segment_count = serializers.IntegerField(source="segments.count", read_only=True)

    class Meta:
        model = Lecture
        fields = [
            "id",
            "title",
            "source_file",
            "description",
            "is_indexed",
            "segment_count",
            "segments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_indexed", "created_at", "updated_at"]


class LectureListSerializer(serializers.ModelSerializer):
    """목록 조회 시 segments를 제외한 경량 시리얼라이저"""

    segment_count = serializers.IntegerField(source="segments.count", read_only=True)

    class Meta:
        model = Lecture
        fields = [
            "id",
            "title",
            "source_file",
            "description",
            "is_indexed",
            "segment_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_indexed", "created_at", "updated_at"]


class BulkImportSegmentSerializer(serializers.Serializer):
    start_time = serializers.CharField(max_length=20)
    end_time = serializers.CharField(max_length=20)
    transcript = serializers.CharField()


class BulkImportSerializer(serializers.Serializer):
    """STT 데이터 일괄 임포트용"""

    title = serializers.CharField(max_length=500)
    source_file = serializers.CharField(max_length=500)
    description = serializers.CharField(required=False, default="")
    segments = BulkImportSegmentSerializer(many=True)

    def validate_segments(self, value):
        if not value:
            raise serializers.ValidationError("최소 1개 이상의 구간이 필요합니다.")
        return value
