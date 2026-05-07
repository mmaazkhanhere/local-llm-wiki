from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def timestamp_iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat()


def approx_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))
