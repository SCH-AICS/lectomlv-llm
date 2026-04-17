from django.urls import path

from . import views

app_name = "lectures"

urlpatterns = [
    path("", views.LectureListCreateView.as_view(), name="lecture-list"),
    path("<int:pk>/", views.LectureDetailView.as_view(), name="lecture-detail"),
    path(
        "<int:lecture_pk>/segments/",
        views.LectureSegmentListView.as_view(),
        name="segment-list",
    ),
    path("bulk-import/", views.BulkImportView.as_view(), name="bulk-import"),
]
