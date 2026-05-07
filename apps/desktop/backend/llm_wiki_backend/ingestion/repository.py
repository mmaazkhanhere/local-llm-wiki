from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from llm_wiki_backend.ingestion.time_utils import approx_token_count, now_iso


def vault_id(vault_path: Path) -> str:
    return hashlib.sha256(str(vault_path.resolve()).encode("utf-8")).hexdigest()


def ensure_vault_row(conn, vault_path: Path) -> str:
    vid = vault_id(vault_path)
    existing = conn.execute("SELECT id FROM vaults WHERE id = ?", (vid,)).fetchone()
    now = now_iso()
    if existing:
        conn.execute("UPDATE vaults SET last_opened_at = ? WHERE id = ?", (now, vid))
        return vid

    conn.execute(
        "INSERT INTO vaults(id, path, created_at, last_opened_at) VALUES(?, ?, ?, ?)",
        (vid, str(vault_path), now, now),
    )
    return vid


def upsert_file(conn, vault_id_value: str, record: dict[str, object]) -> bool:
    row = conn.execute(
        "SELECT id, processing_status FROM files WHERE vault_id = ? AND relative_path = ? LIMIT 1",
        (vault_id_value, record["relative_path"]),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO files(
              id, vault_id, path, relative_path, file_type, sha256, size_bytes, created_at, modified_at,
              last_seen_at, processing_status, last_processed_at, error_message
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                vault_id_value,
                record["path"],
                record["relative_path"],
                record["file_type"],
                "",
                record["size_bytes"],
                record["created_at"],
                record["modified_at"],
                record["last_seen_at"],
                "discovered",
                None,
                None,
            ),
        )
        return True

    current_status = str(row["processing_status"])
    if current_status.startswith("failed"):
        next_status = "discovered"
    elif current_status in {"processed", "pending_image", "unsupported", "extraction_limited", "skipped_unchanged"}:
        next_status = current_status
    else:
        next_status = "discovered"

    conn.execute(
        """
        UPDATE files
        SET path = ?, file_type = ?, size_bytes = ?, created_at = ?, modified_at = ?, last_seen_at = ?, processing_status = ?
        WHERE id = ?
        """,
        (
            record["path"],
            record["file_type"],
            record["size_bytes"],
            record["created_at"],
            record["modified_at"],
            record["last_seen_at"],
            next_status,
            row["id"],
        ),
    )
    return False


def upsert_extraction(conn, file_id: str, title: str | None, extracted_text: str, metadata: dict[str, object]) -> str:
    now = now_iso()
    existing = conn.execute("SELECT id FROM extractions WHERE file_id = ? LIMIT 1", (file_id,)).fetchone()

    if existing is None:
        extraction_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO extractions(id, file_id, title, extracted_text, extraction_metadata_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (extraction_id, file_id, title, extracted_text, json.dumps(metadata), now, now),
        )
        return extraction_id

    extraction_id = existing["id"]
    conn.execute(
        """
        UPDATE extractions
        SET title = ?, extracted_text = ?, extraction_metadata_json = ?, updated_at = ?
        WHERE id = ?
        """,
        (title, extracted_text, json.dumps(metadata), now, extraction_id),
    )
    return extraction_id


def replace_chunks(conn, file_id: str, extraction_id: str, relative_path: str, chunks) -> None:
    chunk_rows = conn.execute("SELECT id FROM chunks WHERE extraction_id = ?", (extraction_id,)).fetchall()
    chunk_ids = [row["id"] for row in chunk_rows]

    conn.execute("DELETE FROM chunks WHERE extraction_id = ?", (extraction_id,))
    if chunk_ids:
        placeholders = ", ".join("?" for _ in chunk_ids)
        conn.execute(f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})", chunk_ids)

    for index, chunk in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        metadata = {
            "relative_path": relative_path,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "page_number": chunk.page_number,
        }
        conn.execute(
            """
            INSERT INTO chunks(id, extraction_id, chunk_index, text, token_count, page_number, heading, metadata_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                extraction_id,
                index,
                chunk.text,
                approx_token_count(chunk.text),
                chunk.page_number,
                chunk.heading,
                json.dumps(metadata),
            ),
        )
        conn.execute(
            """
            INSERT INTO chunks_fts(chunk_id, extraction_id, file_id, relative_path, text, heading, page_number, line_start, line_end)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                extraction_id,
                file_id,
                relative_path,
                chunk.text,
                chunk.heading,
                chunk.page_number,
                chunk.line_start,
                chunk.line_end,
            ),
        )
