from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityItem:
    relative_path: str
    status: str
    last_processed_at: str | None
    error_message: str | None


def recent_generated_files(connection: sqlite3.Connection, limit: int = 10) -> list[ActivityItem]:
    rows = connection.execute(
        """
        SELECT relative_path, processing_status, last_processed_at, error_message
        FROM files
        WHERE processing_status = 'generated'
        ORDER BY COALESCE(last_processed_at, '') DESC, relative_path ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        ActivityItem(
            relative_path=row["relative_path"],
            status=row["processing_status"],
            last_processed_at=row["last_processed_at"],
            error_message=row["error_message"],
        )
        for row in rows
    ]


def recent_errors(connection: sqlite3.Connection, limit: int = 10) -> list[ActivityItem]:
    rows = connection.execute(
        """
        SELECT relative_path, processing_status, last_processed_at, error_message
        FROM files
        WHERE processing_status IN ('failed_transient', 'failed_permanent')
          AND error_message IS NOT NULL
        ORDER BY COALESCE(last_processed_at, '') DESC, relative_path ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        ActivityItem(
            relative_path=row["relative_path"],
            status=row["processing_status"],
            last_processed_at=row["last_processed_at"],
            error_message=row["error_message"],
        )
        for row in rows
    ]
