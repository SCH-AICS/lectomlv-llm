"""외부 JSON 형식을 내부 bulk-import 형식으로 자동 변환

지원하는 외부 JSON 최상위 구조:
{
  "course": {"title": "CAD기초", "language": "ko", ...},
  "summary": {...},
  "materials": [  // PPTX 슬라이드 파일
    {"filename": "...", "slides": [{"page": 1, "text": "..."}]}
  ],
  "videos": [     // 비디오 + STT 세그먼트
    {"filename": "...", "segments": [{"start": 9.5, "end": 33.2, "text": "..."}]}
  ]
}
"""
import math
import re


def seconds_to_timestamp(seconds: float) -> str:
    """초(float) → 'HH:MM:SS' 또는 'MM:SS' 형식으로 변환"""
    total = int(math.floor(seconds))
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _strip_filename(filename: str) -> str:
    """파일명에서 제목 추출: 접두사/확장자 제거"""
    name = re.sub(r"^\(자막\)\s*", "", filename)
    name = re.sub(r"^\[.*?\]\s*", "", name)
    name = re.sub(r"\.\w+$", "", name)
    return name.strip()


def _convert_video(item: dict, course_prefix: str = "") -> dict | None:
    """video/자막 item → bulk-import 형식"""
    segments_raw = item.get("segments", [])
    if not segments_raw:
        return None

    segments = []
    for seg in segments_raw:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        segments.append({
            "start_time": seconds_to_timestamp(seg.get("start", 0)),
            "end_time": seconds_to_timestamp(seg.get("end", 0)),
            "transcript": text,
        })

    if not segments:
        return None

    title = _strip_filename(item.get("filename", "Unknown"))
    if course_prefix:
        title = f"{course_prefix} - {title}"

    return {
        "title": title,
        "source_file": item.get("filename", ""),
        "description": f"video | {item.get('language', 'ko')} | {len(segments)} segments",
        "segments": segments,
    }


def _convert_pptx(item: dict, course_prefix: str = "") -> dict | None:
    """pptx slides → bulk-import 형식 (page 번호를 시간 대신 사용)"""
    slides = item.get("slides", [])
    if not slides:
        return None

    segments = []
    for slide in slides:
        text = (slide.get("text") or "").strip()
        if not text or len(text) < 5:
            continue
        page = slide.get("page", 0)
        segments.append({
            "start_time": f"p{page}",
            "end_time": f"p{page}",
            "transcript": text,
        })

    if not segments:
        return None

    title = _strip_filename(item.get("filename", "Unknown"))
    if course_prefix:
        title = f"{course_prefix} - {title}"

    return {
        "title": title,
        "source_file": item.get("filename", ""),
        "description": f"pptx | {item.get('total_pages', '?')} pages",
        "segments": segments,
    }


def _classify_item(item: dict) -> str:
    """아이템이 pptx인지 video인지 자동 판별"""
    if "slides" in item:
        return "pptx"
    if "segments" in item:
        segs = item["segments"]
        if segs and isinstance(segs[0], dict) and "start" in segs[0]:
            return "video"
    return "unknown"


def detect_and_convert(data: dict | list) -> list[dict]:
    """
    외부 JSON을 자동 감지하여 bulk-import 형식 리스트로 변환.

    지원 형식:
    1. 내부 형식 (title + segments[].transcript) → 그대로 반환
    2. course 래퍼 형식 (course + materials + videos) → 변환
    3. 플랫 형식 (materials/videos/slides_data 키) → 변환
    4. 단일 item / 배열 → 변환
    """
    if isinstance(data, dict) and "title" in data and "segments" in data:
        segs = data.get("segments", [])
        if segs and isinstance(segs[0], dict) and "transcript" in segs[0]:
            return [data]

    results = []
    course_prefix = ""

    if isinstance(data, dict):
        # course 래퍼에서 과정명 추출
        course = data.get("course")
        if isinstance(course, dict):
            course_prefix = course.get("title", "")

        # materials 키: 각 항목을 자동 분류 (pptx/video 혼재 가능)
        for item in data.get("materials", []):
            kind = _classify_item(item)
            if kind == "pptx":
                converted = _convert_pptx(item, course_prefix)
            elif kind == "video":
                converted = _convert_video(item, course_prefix)
            else:
                continue
            if converted:
                results.append(converted)

        # videos 키: 비디오 전용
        for item in data.get("videos", []):
            converted = _convert_video(item, course_prefix)
            if converted:
                results.append(converted)

        # slides_data 키 (이전 호환)
        for item in data.get("slides_data", []):
            converted = _convert_pptx(item, course_prefix)
            if converted:
                results.append(converted)

        # 단일 item fallback
        if not results:
            kind = _classify_item(data)
            if kind == "pptx":
                converted = _convert_pptx(data, course_prefix)
                if converted:
                    results.append(converted)
            elif kind == "video":
                converted = _convert_video(data, course_prefix)
                if converted:
                    results.append(converted)

    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            kind = _classify_item(item)
            if kind == "pptx":
                converted = _convert_pptx(item)
            elif kind == "video":
                converted = _convert_video(item)
            else:
                continue
            if converted:
                results.append(converted)

    return results
