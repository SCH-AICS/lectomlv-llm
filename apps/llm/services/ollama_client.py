import json
import logging
from typing import Generator

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama REST API 클라이언트"""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = httpx.Timeout(timeout=300.0, connect=10.0)

    def _resolve_model(self, model_key: str) -> str:
        return settings.OLLAMA_MODELS.get(model_key, model_key)

    def generate(self, prompt: str, model_key: str = "qwen", system: str = "") -> str:
        model = self._resolve_model(model_key)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        logger.info("Ollama generate: model=%s, prompt_len=%d", model, len(prompt))

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data.get("response", "")

    def generate_stream(
        self, prompt: str, model_key: str = "qwen", system: str = ""
    ) -> Generator[str, None, None]:
        model = self._resolve_model(model_key)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if token := chunk.get("response", ""):
                            yield token

    def chat(
        self, messages: list[dict], model_key: str = "qwen"
    ) -> str:
        model = self._resolve_model(model_key)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data.get("message", {}).get("content", "")

    def list_models(self) -> list[dict]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            return resp.json().get("models", [])

    def pull_model(self, model_name: str) -> dict:
        """Ollama에 모델 다운로드 요청"""
        with httpx.Client(timeout=httpx.Timeout(timeout=3600.0)) as client:
            resp = client.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name, "stream": False},
            )
            resp.raise_for_status()
            return resp.json()

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout=5.0)) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
