from rest_framework import serializers

from .models import LLMQuery


class LLMQueryCreateSerializer(serializers.Serializer):
    query_text = serializers.CharField(help_text="사용자 프롬프트")
    query_type = serializers.ChoiceField(
        choices=["search", "summary", "recommend"],
        help_text="쿼리 유형: search(구간검색), summary(요약), recommend(추천)",
    )
    model_name = serializers.ChoiceField(
        choices=["qwen"],
        default="qwen",
        help_text="사용할 LLM 모델 (qwen=Qwen2.5 14B)",
    )
    lecture_id = serializers.IntegerField(
        required=False,
        help_text="특정 강의 대상 (미지정 시 전체 검색)",
    )


class LLMQueryResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMQuery
        fields = [
            "id",
            "query_text",
            "query_type",
            "model_name",
            "status",
            "task_id",
            "result_text",
            "retrieved_segments",
            "grounding",
            "error_message",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields


