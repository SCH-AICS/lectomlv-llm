import json
import logging
import threading
from pathlib import Path

import faiss
import numpy as np
from django.conf import settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """FAISS 기반 벡터 임베딩 및 검색 서비스 (싱글턴)"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.index_dir = Path(settings.FAISS_INDEX_DIR)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.dimension = settings.EMBEDDING_DIMENSION

        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL_NAME)
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

        self.index = self._load_or_create_index()
        self.metadata = self._load_metadata()

    def _index_path(self) -> Path:
        return self.index_dir / "lecture_index.faiss"

    def _metadata_path(self) -> Path:
        return self.index_dir / "lecture_metadata.json"

    def _load_or_create_index(self) -> faiss.IndexIDMap:
        index_path = self._index_path()
        if index_path.exists():
            logger.info("Loading existing FAISS index from %s", index_path)
            inner = faiss.read_index(str(index_path))
            if isinstance(inner, faiss.IndexIDMap):
                return inner
            index = faiss.IndexIDMap(inner)
            return index

        logger.info("Creating new FAISS index (dim=%d)", self.dimension)
        flat_index = faiss.IndexFlatIP(self.dimension)
        return faiss.IndexIDMap(flat_index)

    def _load_metadata(self) -> dict:
        meta_path = self._metadata_path()
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_index(self):
        faiss.write_index(self.index, str(self._index_path()))
        with open(self._metadata_path(), "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def _next_id(self) -> int:
        if not self.metadata:
            return 0
        return max(int(k) for k in self.metadata.keys()) + 1

    def encode(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings, dtype=np.float32)

    def add_documents(self, texts: list[str], metadatas: list[dict]) -> list[int]:
        """텍스트를 임베딩하고 FAISS 인덱스에 추가"""
        embeddings = self.encode(texts)
        start_id = self._next_id()
        ids = np.array(
            [start_id + i for i in range(len(texts))], dtype=np.int64
        )

        self.index.add_with_ids(embeddings, ids)

        for i, meta in enumerate(metadatas):
            self.metadata[str(ids[i])] = meta

        self._save_index()
        logger.info("Added %d documents to FAISS index", len(texts))
        return ids.tolist()

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """쿼리 텍스트로 유사도 검색"""
        if top_k is None:
            top_k = settings.RAG_TOP_K

        if self.index.ntotal == 0:
            return []

        query_embedding = self.encode([query])
        scores, ids = self.index.search(query_embedding, min(top_k, self.index.ntotal))

        results = []
        for score, doc_id in zip(scores[0], ids[0]):
            if doc_id == -1:
                continue
            meta = self.metadata.get(str(doc_id), {})
            results.append({
                "score": float(score),
                "doc_id": int(doc_id),
                **meta,
            })

        return results

    def delete_by_lecture(self, lecture_id: int):
        """특정 강의의 벡터를 인덱스에서 제거"""
        ids_to_remove = [
            int(k) for k, v in self.metadata.items()
            if v.get("lecture_id") == lecture_id
        ]
        if ids_to_remove:
            self.index.remove_ids(np.array(ids_to_remove, dtype=np.int64))
            for doc_id in ids_to_remove:
                self.metadata.pop(str(doc_id), None)
            self._save_index()
            logger.info("Removed %d vectors for lecture %d", len(ids_to_remove), lecture_id)

    def get_stats(self) -> dict:
        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "metadata_count": len(self.metadata),
        }
