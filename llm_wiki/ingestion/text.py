from __future__ import annotations

from pathlib import Path

from llm_wiki.core.errors import ExtractionTransientError
from llm_wiki.core.retries import FILE_IO_RETRY_POLICY, with_retry


def extract_text(path: Path) -> tuple[str, str, dict[str, str]]:
    def _read_once() -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except PermissionError as exc:
            raise ExtractionTransientError(f"File locked: {path}") from exc

    text = with_retry(_read_once, FILE_IO_RETRY_POLICY)
    title = _title_from_first_nonempty_line(text, fallback=path.stem)
    metadata = {
        "extractor": "text",
        "relative_hint": path.name,
    }
    return title, text, metadata


def _title_from_first_nonempty_line(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return fallback
