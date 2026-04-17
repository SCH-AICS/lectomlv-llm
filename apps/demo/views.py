import requests
from django.conf import settings
from django.views.generic import TemplateView

from apps.lectures.models import Lecture


class DemoView(TemplateView):
    template_name = "demo/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lectures"] = Lecture.objects.order_by("title").values("id", "title")
        ctx["models"] = settings.OLLAMA_MODELS
        return ctx

    def post(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)

        prompt = request.POST.get("prompt", "").strip()
        model_name = request.POST.get("model_name", "qwen")
        query_type = request.POST.get("query_type", "search")
        lecture_id = request.POST.get("lecture_id", "")

        ctx["form_data"] = {
            "prompt": prompt,
            "model_name": model_name,
            "query_type": query_type,
            "lecture_id": lecture_id,
        }

        if not prompt:
            ctx["form_error"] = "프롬프트를 입력하세요."
            return self.render_to_response(ctx)

        body = {
            "query_text": prompt,
            "query_type": query_type,
            "model_name": model_name,
        }
        if lecture_id:
            body["lecture_id"] = int(lecture_id)

        try:
            api_url = "http://127.0.0.1:8000/api/llm/query/"
            res = requests.post(api_url, json=body, timeout=10)
            data = res.json()
            if res.ok:
                ctx["query_id"] = data.get("query_id")
                ctx["active_tab"] = "query"
            else:
                ctx["form_error"] = f"API 오류: {data}"
        except requests.exceptions.JSONDecodeError:
            ctx["form_error"] = f"API 응답 파싱 실패 (status={res.status_code})"
        except Exception as e:
            ctx["form_error"] = f"요청 실패: {e}"

        return self.render_to_response(ctx)
