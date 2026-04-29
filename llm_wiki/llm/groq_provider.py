from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from urllib import error, request

from llm_wiki.core.errors import ProviderPermanentError, ProviderTransientError
from llm_wiki.core.retries import PROVIDER_RETRY_POLICY, with_retry
from llm_wiki.llm.base import LLMProvider, ProviderConfig


class GroqProvider(LLMProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @classmethod
    def from_values(
        cls,
        *,
        api_key: str | None,
        model: str,
        base_url: str = "https://api.groq.com/openai/v1",
    ) -> "GroqProvider":
        resolved_key = api_key or os.environ.get("GROQ_API_KEY", "")
        return cls(
            ProviderConfig(
                api_key=resolved_key.strip(),
                model=model.strip(),
                base_url=base_url.rstrip("/"),
            )
        )

    def provider_name(self) -> str:
        return "groq"

    def supports_vision(self) -> bool:
        return True

    def validate_configuration(self) -> None:
        if not self.config.api_key:
            raise ValueError("Groq API key is missing. Set groq_api_key or GROQ_API_KEY.")
        if not self.config.model:
            raise ValueError("Groq model is missing.")
        if not self.config.base_url.startswith("http"):
            raise ValueError("Groq base URL must be an HTTP URL.")

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        self.validate_configuration()
        payload = {
            "model": self.config.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        return self._request_chat_completion(payload)

    def generate_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        self.validate_configuration()
        path = Path(image_path)
        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "model": self.config.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                },
            ],
        }
        return self._request_chat_completion(payload)

    def _request_chat_completion(self, payload: dict) -> str:
        return with_retry(lambda: self._request_once(payload), PROVIDER_RETRY_POLICY)

    def ping(self) -> tuple[bool, float, str]:
        self.validate_configuration()
        started = time.perf_counter()
        try:
            _ = self.generate_text(
                "You are a concise assistant.",
                "Reply with exactly: pong",
                temperature=0.0,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return True, elapsed_ms, "ok"
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return False, elapsed_ms, str(exc)

    def _request_once(self, payload: dict) -> str:
        url = f"{self.config.base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in {401, 403, 404, 422}:
                raise ProviderPermanentError(f"Groq HTTP {exc.code}: {detail}") from exc
            if exc.code == 429 or 500 <= exc.code < 600:
                raise ProviderTransientError(f"Groq HTTP {exc.code}: {detail}") from exc
            raise ProviderPermanentError(f"Groq HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise ProviderTransientError(f"Groq connection failed: {exc.reason}") from exc

        parsed = json.loads(raw)
        choices = parsed.get("choices", [])
        if not choices:
            raise ProviderPermanentError("Groq response missing choices.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise ProviderPermanentError("Groq response missing content.")
        return content
