from django.contrib import admin

from .models import LLMQuery


@admin.register(LLMQuery)
class LLMQueryAdmin(admin.ModelAdmin):
    list_display = ["id", "query_type", "model_name", "status", "created_at", "completed_at"]
    list_filter = ["query_type", "model_name", "status"]
    search_fields = ["query_text", "result_text"]
    readonly_fields = ["task_id", "created_at", "completed_at"]
