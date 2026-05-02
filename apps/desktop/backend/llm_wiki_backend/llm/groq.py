from __future__ import annotations

import requests


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
