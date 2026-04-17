from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse


@api_view(["GET"])
def api_root(request):
    return Response({
        "lectures": reverse("lectures:lecture-list", request=request),
        "lectures_bulk_import": reverse("lectures:bulk-import", request=request),
        "llm_query": reverse("llm:query-create", request=request),
        "llm_queries": reverse("llm:query-list", request=request),
        "llm_models": reverse("llm:models", request=request),
    })


urlpatterns = [
    path("", include("apps.demo.urls")),
    path("admin/", admin.site.urls),
    path("api/", api_root, name="api-root"),
    path("api/lectures/", include("apps.lectures.urls")),
    path("api/llm/", include("apps.llm.urls")),
]
