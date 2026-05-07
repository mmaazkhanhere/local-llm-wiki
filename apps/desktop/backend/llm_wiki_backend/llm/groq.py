from __future__ import annotations

from typing import Any

import requests

from llm_wiki_backend.llm.provider import LLMProvider


def test_groq_connection(api_key: str, timeout_seconds: float = 10.0) -> tuple[bool, str]:
    url = "https://api.groq.com/openai/v1/models"
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return False, f"Network error: {exc}"
    if response.status_code == 200:
        return True, "Groq connection successful."
    if response.status_code in (401, 403):
        return False, "Groq authentication failed. Check API key."
    return False, f"Groq request failed with status {response.status_code}."


class GroqLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "wiki_generation_plan",
                        "schema": schema,
                    },
                },
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]
