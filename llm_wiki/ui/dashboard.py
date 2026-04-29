from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from llm_wiki.core.config import AppConfig
from llm_wiki.ui.activity import ActivityItem, recent_errors, recent_generated_files


@dataclass(frozen=True)
class DashboardData:
    selected_vault: str
    raw_sources_found: int
    processed_count: int
    queued_or_processing_count: int
    last_processing_time: str | None
    provider_status: str
    recent_generated: list[ActivityItem]
    recent_error_items: list[ActivityItem]


def build_dashboard_data(
    *,
    connection: sqlite3.Connection,
    config: AppConfig,
    vault_root: Path,
) -> DashboardData:
    raw_sources_found = _count_all_files(connection)
    processed_count = _count_processed_files(connection)
    queued_or_processing_count = _count_queued_or_processing(connection)
    last_processing_time = _last_processed_time(connection)
    provider_status = _provider_status(config)
    recent_generated = recent_generated_files(connection, limit=10)
    recent_error_items = recent_errors(connection, limit=10)
    return DashboardData(
        selected_vault=str(vault_root),
        raw_sources_found=raw_sources_found,
        processed_count=processed_count,
        queued_or_processing_count=queued_or_processing_count,
        last_processing_time=last_processing_time,
        provider_status=provider_status,
        recent_generated=recent_generated,
        recent_error_items=recent_error_items,
    )


def render_dashboard_text(data: DashboardData) -> str:
    lines = [
        "LLM Wiki Dashboard",
        f"Selected vault: {data.selected_vault}",
        f"Raw sources found: {data.raw_sources_found}",
        f"Processed: {data.processed_count}",
        f"Queued/Processing: {data.queued_or_processing_count}",
        f"Last processing time: {data.last_processing_time or 'n/a'}",
        f"Provider status: {data.provider_status}",
        "",
        "Recent generated files:",
    ]
    if data.recent_generated:
        for item in data.recent_generated:
            lines.append(f"- {item.relative_path} [{item.status}] {item.last_processed_at or 'n/a'}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Recent errors:")
    if data.recent_error_items:
        for item in data.recent_error_items:
            lines.append(
                f"- {item.relative_path} [{item.status}] {item.error_message or 'n/a'}"
            )
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def _count_all_files(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS c FROM files").fetchone()
    return int(row["c"])


def _count_processed_files(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS c
        FROM files
        WHERE processing_status IN ('generated', 'skipped_unchanged')
        """
    ).fetchone()
    return int(row["c"])


def _count_queued_or_processing(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS c
        FROM files
        WHERE processing_status IN ('queued', 'processing')
        """
    ).fetchone()
    return int(row["c"])


def _last_processed_time(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        """
        SELECT MAX(last_processed_at) AS last_processed
        FROM files
        """
    ).fetchone()
    return row["last_processed"]


def _provider_status(config: AppConfig) -> str:
    if config.provider != "groq":
        return f"unknown-provider:{config.provider}"
    return "configured" if (config.groq_api_key and config.groq_api_key.strip()) else "missing-api-key"
