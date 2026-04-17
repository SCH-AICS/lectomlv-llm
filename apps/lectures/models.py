from django.db import models


class Lecture(models.Model):
    title = models.CharField(max_length=500)
    source_file = models.CharField(
        max_length=500,
        help_text="원본 파일명 (예: p1 1. 인공지능과 기계학습 (Revised).pdf)",
    )
    description = models.TextField(blank=True, default="")
    is_indexed = models.BooleanField(
        default=False,
        help_text="FAISS 벡터 인덱스 반영 여부",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class LectureSegment(models.Model):
    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.CASCADE,
        related_name="segments",
    )
    start_time = models.CharField(max_length=20, help_text="구간 시작 시간 (HH:MM:SS 또는 MM:SS)")
    end_time = models.CharField(max_length=20, help_text="구간 종료 시간")
    transcript = models.TextField(help_text="STT 변환 텍스트")
    embedding_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="FAISS 인덱스 내 벡터 ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lecture", "start_time"]

    def __str__(self):
        return f"[{self.start_time}-{self.end_time}] {self.lecture.title}"

    @property
    def time_range(self):
        return f"{self.start_time}-{self.end_time}"
