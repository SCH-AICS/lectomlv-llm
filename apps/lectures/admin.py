from django.contrib import admin

from .models import Lecture, LectureSegment


class LectureSegmentInline(admin.TabularInline):
    model = LectureSegment
    extra = 0
    readonly_fields = ["embedding_id"]


@admin.register(Lecture)
class LectureAdmin(admin.ModelAdmin):
    list_display = ["title", "source_file", "is_indexed", "created_at"]
    list_filter = ["is_indexed", "created_at"]
    search_fields = ["title", "source_file"]
    inlines = [LectureSegmentInline]


@admin.register(LectureSegment)
class LectureSegmentAdmin(admin.ModelAdmin):
    list_display = ["lecture", "start_time", "end_time", "created_at"]
    list_filter = ["lecture"]
    search_fields = ["transcript"]
