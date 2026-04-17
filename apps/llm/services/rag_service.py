import json
import logging
import re

from django.conf import settings as django_settings

from apps.lectures.models import LectureSegment

from .embedding_service import EmbeddingService
from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)

RELEVANCE_THRESHOLD = getattr(django_settings, "RAG_RELEVANCE_THRESHOLD", 0.25)
CITATION_PATTERN = re.compile(r"\[S(\d+)\]")

GROUNDED_SYSTEM = """\
당신은 대학 강의 자료 기반 Grounded AI 어시스턴트입니다.

## 핵심 규칙 (절대 위반 금지)

1. **오직 제공된 [S#] 출처만 사용하세요.** 출처에 없는 내용은 절대 생성하지 마세요.
2. **모든 주장에 반드시 인라인 인용을 붙이세요.** 형식: [S1], [S2] 등.
   예: "인공지능은 기계가 지능적인 행동을 하는 것입니다 [S2]."
3. **여러 출처가 동일한 내용을 뒷받침하면 모두 표기하세요.** 예: [S1][S3]
4. **출처에서 근거를 찾을 수 없는 질문에는** "제공된 강의 자료에서 해당 내용을 찾을 수 없습니다."라고 답하세요.
5. **답변 마지막에 "## 참조 출처" 섹션을 작성하고**, 실제 인용한 [S#]만 나열하세요.

## 답변 형식

```
(답변 본문 — 모든 문장에 [S#] 인용 포함)

## 참조 출처
- [S1] 파일명 | 시간대
- [S3] 파일명 | 시간대
```"""

SEARCH_TEMPLATE = """\
## 제공된 강의 출처

{context}

---

## 사용자 질문
{query}

---

위 출처만을 근거로, 관련 구간을 찾아 답변하세요.
모든 문장에 [S#] 인용을 반드시 포함하세요."""

SUMMARY_TEMPLATE = """\
## 제공된 강의 출처

{context}

---

## 사용자 요청
{query}

---

위 출처만을 근거로, 핵심 내용을 요약하세요.
요약의 모든 문장에 [S#] 인용을 반드시 포함하세요."""

RECOMMEND_TEMPLATE = """\
## 제공된 강의 출처

{context}

---

## 사용자 요청
{query}

---

위 출처만을 근거로, 학습에 도움이 될 구간이나 주제를 추천하세요.
모든 추천 항목에 [S#] 인용과 추천 이유를 포함하세요."""

PROMPT_TEMPLATES = {
    "search": SEARCH_TEMPLATE,
    "summary": SUMMARY_TEMPLATE,
    "recommend": RECOMMEND_TEMPLATE,
}

FAITHFULNESS_SYSTEM = """\
당신은 Grounded RAG 검증기입니다.
AI 답변의 각 문장이 제공된 출처에 실제로 근거하는지 엄격하게 판단합니다."""

FAITHFULNESS_PROMPT = """\
## 출처 자료
{context}

## AI 답변
{answer}

---

위 답변의 각 문장을 검증하세요. 반드시 아래 JSON 형식으로만 응답하세요.

```json
{{
  "sentences": [
    {{
      "text": "문장 원문",
      "cited_sources": ["S1"],
      "is_grounded": true,
      "reason": "출처 S1의 '...' 부분에 해당 내용 있음"
    }}
  ],
  "overall_grounded": true,
  "ungrounded_count": 0
}}
```

is_grounded 판단 기준:
- true: 해당 문장의 내용이 인용된 출처 텍스트에서 직접 확인 가능
- false: 출처에서 확인 불가하거나, 인용이 없거나, 출처 내용을 왜곡"""


class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.ollama_client = OllamaClient()

    def _retrieve_and_filter(
        self,
        query_text: str,
        lecture_id: int | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        raw_results = self.embedding_service.search(query_text, top_k=top_k)

        if lecture_id:
            raw_results = [r for r in raw_results if r.get("lecture_id") == lecture_id]

        filtered = [r for r in raw_results if r.get("score", 0) >= RELEVANCE_THRESHOLD]

        if not filtered and raw_results:
            filtered = raw_results[:1]

        logger.info(
            "Retrieval: %d raw → %d after threshold(%.2f)",
            len(raw_results), len(filtered), RELEVANCE_THRESHOLD,
        )
        return filtered

    def _build_grounded_context(self, search_results: list[dict]) -> tuple[str, dict]:
        """[S#] 형식의 출처 컨텍스트와 source_map 반환"""
        context_parts = []
        source_map = {}

        for i, result in enumerate(search_results, 1):
            tag = f"S{i}"
            segment_id = result.get("segment_id")
            try:
                segment = LectureSegment.objects.select_related("lecture").get(id=segment_id)
                source_file = segment.lecture.source_file
                start_time = segment.start_time
                end_time = segment.end_time
                transcript = segment.transcript
            except LectureSegment.DoesNotExist:
                source_file = result.get("source_file", "?")
                start_time = result.get("start_time", "?")
                end_time = result.get("end_time", "?")
                transcript = "(원문 없음)"

            context_parts.append(
                f"[{tag}] {source_file} | {start_time} ~ {end_time}\n{transcript}"
            )
            source_map[tag] = {
                "segment_id": segment_id,
                "lecture_id": result.get("lecture_id"),
                "source_file": source_file,
                "start_time": start_time,
                "end_time": end_time,
                "relevance_score": result.get("score"),
                "transcript": transcript,
            }

        return "\n\n".join(context_parts), source_map

    def _generate_grounded_answer(
        self, query_text: str, query_type: str, context: str, model_key: str,
    ) -> str:
        template = PROMPT_TEMPLATES.get(query_type, SEARCH_TEMPLATE)
        prompt = template.format(context=context, query=query_text)
        return self.ollama_client.generate(
            prompt=prompt, model_key=model_key, system=GROUNDED_SYSTEM,
        )

    def _verify_faithfulness(self, answer: str, context: str, model_key: str) -> dict:
        prompt = FAITHFULNESS_PROMPT.format(context=context, answer=answer)
        raw = self.ollama_client.generate(
            prompt=prompt, model_key=model_key, system=FAITHFULNESS_SYSTEM,
        )
        try:
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Faithfulness JSON parse failed, raw: %s", raw[:200])
        return {"sentences": [], "overall_grounded": None, "ungrounded_count": -1}

    def _parse_citations(self, answer: str, source_map: dict) -> dict:
        cited_tags = set(CITATION_PATTERN.findall(answer))
        cited_sources = []
        for tag_num in sorted(cited_tags, key=int):
            tag = f"S{tag_num}"
            if tag in source_map:
                cited_sources.append({**source_map[tag], "citation_tag": f"[{tag}]"})

        uncited_sources = [
            {**v, "citation_tag": f"[{k}]"}
            for k, v in source_map.items()
            if k.lstrip("S") not in cited_tags
        ]

        return {
            "cited_sources": cited_sources,
            "uncited_sources": uncited_sources,
            "total_citations": len(cited_tags),
        }

    @staticmethod
    def _build_segment_list(citation_info: dict) -> list[dict]:
        fields = (
            "segment_id", "lecture_id", "start_time", "end_time",
            "source_file", "relevance_score", "citation_tag",
        )
        segments = []
        for src in citation_info["cited_sources"]:
            segments.append({k: src.get(k) for k in fields} | {"cited": True})
        for src in citation_info["uncited_sources"]:
            segments.append({k: src.get(k) for k in fields} | {"cited": False})
        return segments

    def process_query(
        self,
        query_text: str,
        query_type: str,
        model_key: str = "qwen",
        lecture_id: int | None = None,
        top_k: int | None = None,
    ) -> dict:
        """Grounded RAG 파이프라인: 검색 → 생성(인용) → 검증 → 구조화"""
        search_results = self._retrieve_and_filter(query_text, lecture_id, top_k)

        if not search_results:
            return {
                "result_text": "관련된 강의 내용을 찾을 수 없습니다. 다른 검색어로 시도해 주세요.",
                "retrieved_segments": [],
                "grounding": {"verified": False, "reason": "no_sources"},
            }

        context, source_map = self._build_grounded_context(search_results)
        logger.info(
            "Grounded RAG: type=%s, model=%s, sources=%d",
            query_type, model_key, len(source_map),
        )

        answer = self._generate_grounded_answer(query_text, query_type, context, model_key)
        citation_info = self._parse_citations(answer, source_map)
        verification = self._verify_faithfulness(answer, context, model_key)

        overall_grounded = verification.get("overall_grounded")
        ungrounded_count = verification.get("ungrounded_count", -1)

        grounding_result = {
            "verified": overall_grounded is True,
            "overall_grounded": overall_grounded,
            "ungrounded_count": ungrounded_count,
            "total_citations": citation_info["total_citations"],
            "verification_details": verification.get("sentences", []),
        }

        if overall_grounded is False and ungrounded_count > 0:
            answer += (
                f"\n\n---\n⚠️ 검증 결과: {ungrounded_count}개 문장이 "
                f"출처에서 확인되지 않았습니다. 해당 부분은 주의하여 참고하세요."
            )

        return {
            "result_text": answer,
            "retrieved_segments": self._build_segment_list(citation_info),
            "grounding": grounding_result,
        }
