from __future__ import annotations

import requests

from llm_wiki_backend.security.secrets import load_groq_key


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


def generate_candidate_response(
    *,
    vault_path,
    model_id: str,
    source_title: str,
    relative_path: str,
    extracted_text: str,
    timeout_seconds: float = 45.0,
) -> str:
    api_key = load_groq_key(vault_path)
    prompt = _candidate_prompt(source_title=source_title, relative_path=relative_path, extracted_text=extracted_text)
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_id,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate concise Obsidian wiki candidates from extracted source text. "
                        "Return strict JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Groq response did not include choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Groq response did not include text content.")
    return content


def _candidate_prompt(*, source_title: str, relative_path: str, extracted_text: str) -> str:
    return f"""
Analyze the extracted source and identify concise wiki candidates.

Source title: {source_title}
Source path: {relative_path}

Return JSON with this exact top-level shape:
{{
  "concepts": [{{
    "title": "...",
    "summary": "...",
    "why_it_matters": "...",
    "how_it_works": ["..."],
    "examples": ["..."],
    "use_cases": ["..."],
    "failure_modes": ["..."],
    "body": ["claim-level statements..."],
    "links": ["..."],
    "source_notes": ["..."]
  }}],
  "entities": [{{"title": "...", "summary": "...", "body": ["..."], "links": ["..."], "source_notes": ["..."]}}],
  "comparisons": [{{"title": "...", "summary": "...", "body": ["..."], "links": ["..."], "source_notes": ["..."]}}],
  "maps": [{{"title": "...", "summary": "...", "body": ["..."], "links": ["..."], "source_notes": ["..."]}}],
  "flashcards": [{{"title": "...", "question": "...", "answer": "...", "related_pages": ["..."], "source_notes": ["..."]}}]
}}

Rules:
- Keep summaries concise.
- For concepts, provide practical examples and failure modes when present in source.
- Use links only for relevant wiki targets.
- Only emit useful candidates.
- Do not create a page candidate unless it has reusable meaning and enough substance.
- Source notes should mention a section, page, or line anchor when practical.
- Do not return markdown fences.

Extracted text:
{extracted_text}
""".strip()
