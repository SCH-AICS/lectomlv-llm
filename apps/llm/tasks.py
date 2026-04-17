import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def process_llm_query(self, query_id: int, lecture_id: int | None = None):
    """LLM 쿼리를 비동기로 처리 (RAG 파이프라인)"""
    from apps.llm.models import LLMQuery, QueryStatus
    from apps.llm.services.rag_service import RAGService

    try:
        query = LLMQuery.objects.get(id=query_id)
        query.status = QueryStatus.PROCESSING
        query.save(update_fields=["status"])

        rag = RAGService()
        result = rag.process_query(
            query_text=query.query_text,
            query_type=query.query_type,
            model_key=query.model_name,
            lecture_id=lecture_id,
        )

        query.result_text = result["result_text"]
        query.retrieved_segments = result["retrieved_segments"]
        query.grounding = result.get("grounding", {})
        query.status = QueryStatus.COMPLETED
        query.completed_at = timezone.now()
        query.save(update_fields=[
            "result_text", "retrieved_segments", "grounding", "status", "completed_at"
        ])

        grounding = result.get("grounding", {})
        logger.info(
            "Query %d completed — grounded=%s, citations=%d, ungrounded=%d",
            query_id,
            grounding.get("overall_grounded"),
            grounding.get("total_citations", 0),
            grounding.get("ungrounded_count", 0),
        )
        return {
            "query_id": query_id,
            "status": "completed",
            "segments_found": len(result["retrieved_segments"]),
            "grounded": grounding.get("overall_grounded"),
        }

    except LLMQuery.DoesNotExist:
        logger.error("Query %d not found", query_id)
        return {"query_id": query_id, "status": "error", "message": "Query not found"}

    except Exception as exc:
        logger.exception("Query %d failed", query_id)
        try:
            query = LLMQuery.objects.get(id=query_id)
            query.status = QueryStatus.FAILED
            query.error_message = str(exc)
            query.save(update_fields=["status", "error_message"])
        except LLMQuery.DoesNotExist:
            pass
        raise self.retry(exc=exc, countdown=60)
