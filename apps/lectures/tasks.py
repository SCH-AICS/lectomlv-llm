import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def index_lecture_segments(self, lecture_id: int):
    """강의 세그먼트를 FAISS 벡터 인덱스에 추가"""
    from apps.lectures.models import Lecture, LectureSegment
    from apps.llm.services.embedding_service import EmbeddingService

    try:
        lecture = Lecture.objects.get(id=lecture_id)
        segments = LectureSegment.objects.filter(lecture=lecture)

        if not segments.exists():
            logger.warning("Lecture %d has no segments to index", lecture_id)
            return {"status": "skipped", "reason": "no segments"}

        service = EmbeddingService()
        texts = [seg.transcript for seg in segments]
        metadatas = [
            {
                "segment_id": seg.id,
                "lecture_id": lecture.id,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "source_file": lecture.source_file,
            }
            for seg in segments
        ]

        ids = service.add_documents(texts, metadatas)

        for seg, emb_id in zip(segments, ids):
            seg.embedding_id = emb_id
        LectureSegment.objects.bulk_update(segments, ["embedding_id"])

        lecture.is_indexed = True
        lecture.save(update_fields=["is_indexed"])

        logger.info("Indexed %d segments for lecture %d", len(ids), lecture_id)
        return {"status": "completed", "indexed_count": len(ids)}

    except Exception as exc:
        logger.exception("Failed to index lecture %d", lecture_id)
        raise self.retry(exc=exc, countdown=30)
