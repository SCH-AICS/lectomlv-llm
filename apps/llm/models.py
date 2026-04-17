from django.db import models


class QueryType(models.TextChoices):
    SEARCH = "search", "구간 검색"
    SUMMARY = "summary", "요약"
    RECOMMEND = "recommend", "추천"


class QueryStatus(models.TextChoices):
    PENDING = "pending", "대기 중"
    PROCESSING = "processing", "처리 중"
    COMPLETED = "completed", "완료"
    FAILED = "failed", "실패"


class LLMQuery(models.Model):
    query_text = models.TextField(help_text="사용자 프롬프트")
    query_type = models.CharField(
        max_length=20,
        choices=QueryType.choices,
        default=QueryType.SEARCH,
    )
    model_name = models.CharField(
        max_length=100,
        help_text="사용할 Ollama 모델 키 (예: qwen, gemma)",
    )
    status = models.CharField(
        max_length=20,
        choices=QueryStatus.choices,
        default=QueryStatus.PENDING,
    )
    task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Celery 태스크 ID",
    )

    # 결과
    result_text = models.TextField(blank=True, default="")
    retrieved_segments = models.JSONField(
        default=list,
        blank=True,
        help_text="RAG로 검색된 세그먼트 정보",
    )
    grounding = models.JSONField(
        default=dict,
        blank=True,
        help_text="Grounded RAG 검증 결과 (faithfulness, citation 정보)",
    )
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "LLM 쿼리"
        verbose_name_plural = "LLM 쿼리들"

    def __str__(self):
        return f"[{self.query_type}] {self.query_text[:50]}"
