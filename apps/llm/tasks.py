import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def process_llm_query(self, query_id: int, lecture_id: int | None = None):
    """LLM 쿼리를 비동기로 처리 (RAG 파이프라인).

    RAG 완료 후, 인용된 출처 중 영상 파일이 있으면
    clip_video_segments 태스크를 비동기로 dispatch 한다.
    """
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


@shared_task(bind=True, max_retries=1)
def merge_video_clips(self, query_id: int):
    """
    query 의 video_clips 중 성공한 클립들을 하나로 합침.
    완료 후 LLMQuery.merged_clip 필드를 업데이트한다.
    """
    from apps.llm.models import LLMQuery
    from apps.llm.services.video_clip_service import VideoClipService

    logger.info("Query %d: 클립 머지 시작", query_id)
    try:
        query = LLMQuery.objects.get(pk=query_id)
        service = VideoClipService()
        result = service.merge_clips(query.video_clips or [], query_id)

        LLMQuery.objects.filter(pk=query_id).update(merged_clip=result)
        logger.info("Query %d: 머지 완료 — status=%s", query_id, result.get("status"))
        return {"query_id": query_id, "status": result.get("status")}
    except LLMQuery.DoesNotExist:
        logger.error("Query %d not found", query_id)
        return {"query_id": query_id, "status": "error"}
    except Exception as exc:
        logger.exception("Query %d 머지 실패", query_id)
        raise self.retry(exc=exc, countdown=15)


@shared_task(bind=True, max_retries=1)
def clip_video_segments(self, query_id: int, cited_sources: list[dict]):
    """
    RAG 인용 출처 중 영상 파일에 해당하는 구간을 ffmpeg으로 잘라 클립을 생성.

    Parameters
    ----------
    query_id : int
        LLMQuery PK — 완료 후 video_clips 필드를 업데이트한다.
    cited_sources : list[dict]
        process_llm_query 에서 넘겨온 cited=True 세그먼트 목록.
        각 항목에 source_file, start_time, end_time, citation_tag 포함.
    """
    from apps.llm.models import LLMQuery
    from apps.llm.services.video_clip_service import VideoClipService

    logger.info("Query %d: 영상 클리핑 시작 (%d개)", query_id, len(cited_sources))
    try:
        service = VideoClipService()
        clips = service.make_clips(cited_sources)

        if not clips:
            logger.info("Query %d: 영상 출처 없음, 클리핑 건너뜀", query_id)
            return {"query_id": query_id, "clips": 0}

        LLMQuery.objects.filter(id=query_id).update(video_clips=clips)

        success = sum(1 for c in clips if c["status"] == "success")
        logger.info(
            "Query %d: 클리핑 완료 — 성공 %d / 전체 %d",
            query_id, success, len(clips),
        )
        return {"query_id": query_id, "clips": len(clips), "success": success}

    except Exception as exc:
        logger.exception("Query %d 클리핑 실패", query_id)
        raise self.retry(exc=exc, countdown=30)
