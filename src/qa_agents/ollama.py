from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """Raised when Ollama cannot complete a request."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: int = 300,
        temperature: float = 0.1,
        context_window: int = 16_384,
        max_output_tokens: int = 8_192,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.context_window = context_window
        self.max_output_tokens = max_output_tokens

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/api/tags")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
        images_base64: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        user_message: dict[str, Any] = {"role": "user", "content": user_prompt}
        if images_base64:
            user_message["images"] = images_base64

        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                user_message,
            ],
            "stream": False,
            "format": response_schema,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.context_window,
                "num_predict": self.max_output_tokens,
            },
        }
        response = self._request("POST", "/api/chat", payload)
        try:
            return response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaError(f"Unexpected Ollama response: {response}") from exc

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise OllamaError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise OllamaError(
                f"Cannot reach Ollama at {self.base_url}. Start Ollama and pull model "
                f"'{self.model}'. Original error: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise OllamaError(
                f"Ollama did not finish within {self.timeout_seconds} seconds. "
                "Try a smaller source document, request fewer test cases, or increase "
                "OLLAMA_TIMEOUT_SECONDS."
            ) from exc
