from celery.result import AsyncResult
from django.conf import settings
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LLMQuery
from .serializers import LLMQueryCreateSerializer, LLMQueryResultSerializer
from .tasks import process_llm_query


class LLMQueryView(APIView):
    """LLM 쿼리 생성 (비동기 처리)"""

    def post(self, request):
        serializer = LLMQueryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        query = LLMQuery.objects.create(
            query_text=data["query_text"],
            query_type=data["query_type"],
            model_name=data["model_name"],
        )

        task = process_llm_query.delay(
            query_id=query.id,
            lecture_id=data.get("lecture_id"),
        )

        query.task_id = task.id
        query.save(update_fields=["task_id"])

        return Response(
            {
                "query_id": query.id,
                "task_id": task.id,
                "status": "pending",
                "message": "쿼리가 접수되었습니다. task_id로 결과를 조회하세요.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class LLMQueryDetailView(generics.RetrieveAPIView):
    """쿼리 결과 조회"""

    queryset = LLMQuery.objects.all()
    serializer_class = LLMQueryResultSerializer


class TaskStatusView(APIView):
    """Celery 태스크 상태 확인"""

    def get(self, request, task_id):
        result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": result.status,
        }

        if result.ready():
            if result.successful():
                response_data["result"] = result.result
            else:
                response_data["error"] = str(result.result)

        query = LLMQuery.objects.filter(task_id=task_id).first()
        if query:
            response_data["query_id"] = query.id
            response_data["query_status"] = query.status
            if query.status == "completed":
                response_data["result_text"] = query.result_text
                response_data["retrieved_segments"] = query.retrieved_segments

        return Response(response_data)


class AvailableModelsView(APIView):
    """사용 가능한 LLM 모델 목록"""

    def get(self, request):
        models = {
            key: {"model_id": value, "key": key}
            for key, value in settings.OLLAMA_MODELS.items()
        }
        return Response(
            {
                "models": models,
                "default": settings.OLLAMA_DEFAULT_MODEL,
            }
        )


class LLMQueryListView(generics.ListAPIView):
    """쿼리 이력 조회"""

    queryset = LLMQuery.objects.all()
    serializer_class = LLMQueryResultSerializer
