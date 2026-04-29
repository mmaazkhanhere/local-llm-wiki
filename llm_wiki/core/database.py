from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from llm_wiki.core.scanner import ScannedFile


FILE_STATUS_DISCOVERED = "discovered"
FILE_STATUS_QUEUED = "queued"
FILE_STATUS_PROCESSING = "processing"
FILE_STATUS_GENERATED = "generated"
FILE_STATUS_SKIPPED_UNCHANGED = "skipped_unchanged"
FILE_STATUS_FAILED_TRANSIENT = "failed_transient"
FILE_STATUS_FAILED_PERMANENT = "failed_permanent"


@dataclass(frozen=True)
class Database:
    path: Path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def initialize_schema(connection: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS vaults (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_opened_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            vault_id TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER,
            created_at TEXT,
            modified_at TEXT,
            last_seen_at TEXT,
            processing_status TEXT NOT NULL,
            last_processed_at TEXT,
            error_message TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS source_documents (
            id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            title TEXT,
            extracted_text TEXT,
            extraction_metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            source_document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            token_count INTEGER,
            page_number INTEGER,
            heading TEXT,
            metadata_json TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS generated_pages (
            id TEXT PRIMARY KEY,
            source_document_id TEXT,
            page_type TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            sha256 TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            target_path TEXT,
            source_paths_json TEXT,
            summary TEXT NOT NULL,
            details_json TEXT,
            created_at TEXT NOT NULL
        )
        """,
    )
    for statement in statements:
        connection.execute(statement)
    connection.commit()


def upsert_vault(connection: sqlite3.Connection, vault_path: Path) -> str:
    row = connection.execute(
        "SELECT id FROM vaults WHERE path = ?",
        (str(vault_path),),
    ).fetchone()
    now = utc_now_iso()
    if row:
        vault_id = row["id"]
        connection.execute(
            "UPDATE vaults SET last_opened_at = ? WHERE id = ?",
            (now, vault_id),
        )
        connection.commit()
        return vault_id
    vault_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO vaults (id, path, created_at, last_opened_at)
        VALUES (?, ?, ?, ?)
        """,
        (vault_id, str(vault_path), now, now),
    )
    connection.commit()
    return vault_id


def upsert_scanned_file(
    connection: sqlite3.Connection,
    vault_id: str,
    scanned: ScannedFile,
    sha256: str,
    status: str = FILE_STATUS_DISCOVERED,
    error_message: str | None = None,
) -> str:
    now = utc_now_iso()
    row = connection.execute(
        "SELECT id FROM files WHERE vault_id = ? AND relative_path = ?",
        (vault_id, scanned.relative_path.as_posix()),
    ).fetchone()
    if row:
        file_id = row["id"]
        connection.execute(
            """
            UPDATE files
            SET path = ?, file_type = ?, sha256 = ?, size_bytes = ?, last_seen_at = ?,
                processing_status = ?, error_message = ?
            WHERE id = ?
            """,
            (
                str(scanned.path),
                scanned.extension,
                sha256,
                scanned.size_bytes,
                now,
                status,
                error_message,
                file_id,
            ),
        )
        connection.commit()
        return file_id
    file_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO files (
            id, vault_id, path, relative_path, file_type, sha256, size_bytes,
            created_at, modified_at, last_seen_at, processing_status, last_processed_at, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            vault_id,
            str(scanned.path),
            scanned.relative_path.as_posix(),
            scanned.extension,
            sha256,
            scanned.size_bytes,
            now,
            None,
            now,
            status,
            None,
            error_message,
        ),
    )
    connection.commit()
    return file_id


def get_file_by_relative_path(
    connection: sqlite3.Connection,
    vault_id: str,
    relative_path: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT id, sha256, processing_status, error_message, last_processed_at
        FROM files
        WHERE vault_id = ? AND relative_path = ?
        """,
        (vault_id, relative_path),
    ).fetchone()


def set_file_status(
    connection: sqlite3.Connection,
    file_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    now = utc_now_iso()
    last_processed_at = now if status in {FILE_STATUS_GENERATED, FILE_STATUS_FAILED_PERMANENT, FILE_STATUS_FAILED_TRANSIENT} else None
    connection.execute(
        """
        UPDATE files
        SET processing_status = ?, error_message = ?, last_processed_at = COALESCE(?, last_processed_at)
        WHERE id = ?
        """,
        (status, error_message, last_processed_at, file_id),
    )
    connection.commit()


def upsert_source_document(
    connection: sqlite3.Connection,
    file_id: str,
    title: str,
    extracted_text: str,
    extraction_metadata: dict[str, str | int | float | bool | None],
) -> str:
    now = utc_now_iso()
    row = connection.execute(
        "SELECT id FROM source_documents WHERE file_id = ?",
        (file_id,),
    ).fetchone()
    metadata_json = json.dumps(extraction_metadata, ensure_ascii=True)
    if row:
        source_document_id = row["id"]
        connection.execute(
            """
            UPDATE source_documents
            SET title = ?, extracted_text = ?, extraction_metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, extracted_text, metadata_json, now, source_document_id),
        )
        connection.commit()
        return source_document_id

    source_document_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO source_documents (
            id, file_id, title, extracted_text, extraction_metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (source_document_id, file_id, title, extracted_text, metadata_json, now, now),
    )
    connection.commit()
    return source_document_id


def replace_chunks(
    connection: sqlite3.Connection,
    source_document_id: str,
    chunks: list[str],
) -> None:
    connection.execute(
        "DELETE FROM chunks WHERE source_document_id = ?",
        (source_document_id,),
    )
    for index, chunk_text in enumerate(chunks):
        connection.execute(
            """
            INSERT INTO chunks (
                id, source_document_id, chunk_index, text, token_count, page_number, heading, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                source_document_id,
                index,
                chunk_text,
                len(chunk_text.split()),
                None,
                None,
                "{}",
            ),
        )
    connection.commit()


def upsert_generated_page(
    connection: sqlite3.Connection,
    source_document_id: str,
    page_type: str,
    path: Path,
    relative_path: str,
    sha256: str,
    status: str = "generated",
) -> str:
    now = utc_now_iso()
    row = connection.execute(
        """
        SELECT id FROM generated_pages
        WHERE source_document_id = ? AND page_type = ?
        """,
        (source_document_id, page_type),
    ).fetchone()
    if row:
        page_id = row["id"]
        connection.execute(
            """
            UPDATE generated_pages
            SET path = ?, relative_path = ?, sha256 = ?, updated_at = ?, status = ?
            WHERE id = ?
            """,
            (str(path), relative_path, sha256, now, status, page_id),
        )
        connection.commit()
        return page_id

    page_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO generated_pages (
            id, source_document_id, page_type, path, relative_path, sha256, created_at, updated_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (page_id, source_document_id, page_type, str(path), relative_path, sha256, now, now, status),
    )
    connection.commit()
    return page_id


def insert_audit_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    target_path: str,
    source_paths: list[str],
    summary: str,
    details: dict[str, str],
) -> str:
    audit_id = str(uuid4())
    now = utc_now_iso()
    connection.execute(
        """
        INSERT INTO audit_log (
            id, event_type, target_path, source_paths_json, summary, details_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            event_type,
            target_path,
            json.dumps(source_paths, ensure_ascii=True),
            summary,
            json.dumps(details, ensure_ascii=True),
            now,
        ),
    )
    connection.commit()
    return audit_id
