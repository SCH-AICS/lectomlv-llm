from django.urls import path

from . import views

app_name = "llm"

urlpatterns = [
    path("query/", views.LLMQueryView.as_view(), name="query-create"),
    path("query/<int:pk>/", views.LLMQueryDetailView.as_view(), name="query-detail"),
    path("queries/", views.LLMQueryListView.as_view(), name="query-list"),
    path("tasks/<str:task_id>/", views.TaskStatusView.as_view(), name="task-status"),
    path("models/", views.AvailableModelsView.as_view(), name="models"),
]
