from __future__ import annotations

from datetime import UTC, datetime


def render_source_summary_page(
    *,
    source_title: str,
    relative_source_path: str,
    summary_markdown_body: str,
) -> str:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    body = summary_markdown_body.strip()
    return (
        f"# {source_title} Summary\n\n"
        f"Source: `{relative_source_path}`\n"
        f"Generated: {timestamp}\n"
        "Status: LLM-generated\n\n"
        f"{body}\n"
    )
