import logging
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from django.conf import settings as django_settings

_FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

# MM:SS  또는  HH:MM:SS  또는  소수점 포함 변형 모두 허용
_TIME_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$")


def _parse_time_to_seconds(time_str: str) -> float:
    """
    시간 문자열을 초(float)로 변환.
    지원 형식: MM:SS, HH:MM:SS, MM:SS.sss
    """
    m = _TIME_RE.match(time_str.strip())
    if not m:
        raise ValueError(f"인식할 수 없는 시간 형식: {time_str!r}")
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _is_video_file(source_file: str) -> bool:
    """파일 확장자로 영상 파일 여부 판단"""
    return Path(source_file).suffix.lower() in VIDEO_EXTENSIONS


def _find_video_path(source_file: str, video_dir: Path) -> Path | None:
    """
    video_dir 에서 source_file 이름과 일치하는 파일을 탐색.
    - 정확 일치 우선
    - 없으면 줄기 이름(stem) 기준 대소문자 무시 탐색
    """
    exact = video_dir / source_file
    if exact.exists():
        return exact

    stem_lower = Path(source_file).stem.lower()
    for candidate in video_dir.iterdir():
        if candidate.is_file() and candidate.stem.lower() == stem_lower:
            return candidate

    return None


def _safe_filename(time_str: str) -> str:
    """시간 문자열을 파일명에 안전한 문자열로 변환. 47:05 → 47-05"""
    return time_str.replace(":", "-").replace(".", "_")


class VideoClipService:
    """
    RAG 인용 출처에서 영상 구간을 찾아 ffmpeg으로 클립을 생성하는 서비스.

    VIDEO_SOURCE_DIR : 원본 영상 파일이 모여있는 디렉터리 (읽기 전용)
    VIDEO_CLIPS_DIR  : 생성된 클립을 저장할 디렉터리
    """

    def __init__(self):
        self.video_dir = Path(
            getattr(django_settings, "VIDEO_SOURCE_DIR", "/data/videos")
        )
        self.clips_dir = Path(
            getattr(django_settings, "VIDEO_CLIPS_DIR", "/data/clips")
        )
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------

    def merge_clips(self, video_clips: list[dict], query_id: int) -> dict:
        """
        성공한 클립들을 시간순으로 이어붙여 하나의 mp4로 합친다.

        Returns
        -------
        dict
            {
                "merged_filename": "merged_42.mp4",
                "merged_url":      "/clips/merged_42.mp4",
                "status":          "success" | "failed" | "nothing_to_merge",
                "error":           "...",  # 실패 시
            }
        """
        success_clips = [c for c in video_clips if c.get("status") == "success" and c.get("clip_filename")]
        if not success_clips:
            return {"status": "nothing_to_merge", "error": "성공한 클립이 없습니다."}

        merged_filename = f"merged_{query_id}.mp4"
        output_path = self.clips_dir / merged_filename

        if len(success_clips) == 1:
            # 클립이 하나면 그대로 복사
            import shutil
            src = self.clips_dir / success_clips[0]["clip_filename"]
            if src.exists():
                shutil.copy2(src, output_path)
                return {"merged_filename": merged_filename, "merged_url": f"/clips/{merged_filename}", "status": "success"}
            return {"status": "failed", "error": "원본 클립 파일을 찾을 수 없음"}

        # 임시 filelist 작성
        filelist_path = self.clips_dir / f"_filelist_{query_id}.txt"
        try:
            lines = []
            for clip in success_clips:
                clip_path = self.clips_dir / clip["clip_filename"]
                if clip_path.exists():
                    lines.append(f"file '{clip_path}'")
            if not lines:
                return {"status": "failed", "error": "클립 파일이 존재하지 않습니다."}

            filelist_path.write_text("\n".join(lines), encoding="utf-8")
            ok = self._run_concat(filelist_path, output_path)
        finally:
            if filelist_path.exists():
                filelist_path.unlink()

        if ok:
            return {"merged_filename": merged_filename, "merged_url": f"/clips/{merged_filename}", "status": "success"}
        return {"status": "failed", "error": "ffmpeg concat 실패 (로그 확인)"}

    def make_clips(self, cited_sources: list[dict]) -> list[dict]:
        """
        cited_sources 목록에서 영상 출처만 골라 ffmpeg 클리핑을 수행.

        Parameters
        ----------
        cited_sources : list[dict]
            RAG 파이프라인이 반환한 cited_sources 리스트.
            각 항목에 source_file, start_time, end_time, citation_tag 가 있어야 함.

        Returns
        -------
        list[dict]
            클리핑 결과 목록. 각 항목 구조:
            {
                "citation_tag": "[S1]",
                "source_file":  "CS231_Lecture6.mp4",
                "start_time":   "47:05",
                "end_time":     "47:14",
                "clip_filename": "CS231_Lecture6_47-05_47-14.mp4",
                "clip_url":     "/clips/CS231_Lecture6_47-05_47-14.mp4",
                "status":       "success" | "skipped" | "not_found" | "failed",
                "error":        "오류 메시지 (실패 시에만)",
            }
        """
        results = []
        for src in cited_sources:
            result = self._process_one(src)
            if result is not None:
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _process_one(self, src: dict) -> dict | None:
        source_file = src.get("source_file", "")
        start_time = src.get("start_time", "")
        end_time = src.get("end_time", "")
        tag = src.get("citation_tag", "")

        if not _is_video_file(source_file):
            return None  # 영상 파일이 아니면 처리 skip

        base = {
            "citation_tag": tag,
            "source_file": source_file,
            "start_time": start_time,
            "end_time": end_time,
        }

        video_path = _find_video_path(source_file, self.video_dir)
        if video_path is None:
            logger.warning("원본 영상을 찾을 수 없음: %s (탐색 경로: %s)", source_file, self.video_dir)
            return {**base, "status": "not_found", "error": f"{self.video_dir} 에서 파일을 찾을 수 없음"}

        try:
            start_sec = _parse_time_to_seconds(start_time)
            end_sec = _parse_time_to_seconds(end_time)
        except ValueError as exc:
            logger.warning("시간 파싱 실패 (%s ~ %s): %s", start_time, end_time, exc)
            return {**base, "status": "failed", "error": str(exc)}

        if end_sec <= start_sec:
            return {**base, "status": "failed", "error": "end_time 이 start_time 보다 앞서거나 같음"}

        clip_filename = self._build_clip_filename(source_file, start_time, end_time)
        output_path = self.clips_dir / clip_filename

        if output_path.exists():
            logger.info("클립 이미 존재, 재사용: %s", clip_filename)
            return {**base, "clip_filename": clip_filename, "clip_url": f"/clips/{clip_filename}", "status": "success"}

        success = self._run_ffmpeg(video_path, start_sec, end_sec, output_path)
        if success:
            return {**base, "clip_filename": clip_filename, "clip_url": f"/clips/{clip_filename}", "status": "success"}
        else:
            return {**base, "status": "failed", "error": "ffmpeg 실행 실패 (로그 확인)"}

    @staticmethod
    def _build_clip_filename(source_file: str, start_time: str, end_time: str) -> str:
        stem = Path(source_file).stem
        s = _safe_filename(start_time)
        e = _safe_filename(end_time)
        # 파일명이 너무 길어지지 않도록 stem 을 100자로 제한
        return f"{stem[:100]}_{s}_{e}.mp4"

    @staticmethod
    def _run_ffmpeg(input_path: Path, start_sec: float, end_sec: float, output_path: Path) -> bool:
        """
        ffmpeg -ss {start} -i {input} -t {duration} -c copy -avoid_negative_ts make_zero -y {output}

        -ss 를 -i 앞에 배치해 고속 seek 후, -c copy 로 재인코딩 없이 잘라냄.
        키프레임 경계 문제로 정확도가 약간 떨어질 수 있으나 속도가 빠름.
        """
        duration = end_sec - start_sec
        cmd = [
            _FFMPEG_BIN,
            "-ss", str(start_sec),
            "-i", str(input_path),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path),
        ]
        logger.info("ffmpeg 실행: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5분 제한
            )
            if proc.returncode != 0:
                logger.error("ffmpeg 오류 (returncode=%d):\n%s", proc.returncode, proc.stderr[-2000:])
                return False
            logger.info("클립 생성 완료: %s", output_path.name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg 타임아웃: %s", input_path.name)
            return False
        except FileNotFoundError:
            logger.error("ffmpeg 바이너리를 찾을 수 없음: %s", _FFMPEG_BIN)
            return False

    @staticmethod
    def _run_concat(filelist_path: Path, output_path: Path) -> bool:
        """ffmpeg concat demuxer로 클립들을 하나로 합침 (재인코딩 없음)"""
        cmd = [
            _FFMPEG_BIN,
            "-f", "concat",
            "-safe", "0",
            "-i", str(filelist_path),
            "-c", "copy",
            "-y",
            str(output_path),
        ]
        logger.info("ffmpeg concat 실행: %d개 클립 → %s", sum(1 for _ in filelist_path.read_text().splitlines()), output_path.name)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                logger.error("ffmpeg concat 오류 (returncode=%d):\n%s", proc.returncode, proc.stderr[-2000:])
                return False
            logger.info("머지 완료: %s", output_path.name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg concat 타임아웃")
            return False
        except FileNotFoundError:
            logger.error("ffmpeg 바이너리를 찾을 수 없음: %s", _FFMPEG_BIN)
            return False
