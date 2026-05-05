from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.ingestion.extractors import extract_file, supported_file_type
from llm_wiki_backend.ingestion.types import FileSnapshot, ProcessSummary

PROTECTED_FOLDERS = {"wiki", ".llm-wiki", ".obsidian", ".git", ".trash"}


def scan_raw_files(vault_path: Path) -> ProcessSummary:
    discovered_count = 0
    with connect_database(vault_path) as conn:
        vault_id = _ensure_vault_row(conn, vault_path)
        for file_path in _iter_raw_files(vault_path):
            relative = file_path.relative_to(vault_path)
            if _is_protected_relative(relative):
                continue
            file_type = supported_file_type(file_path)
            stat = file_path.stat()
            now = _now_iso()
            record = {
                "path": str(file_path),
                "relative_path": relative.as_posix(),
                "file_type": file_type,
                "size_bytes": int(stat.st_size),
                "created_at": _timestamp_iso(stat.st_ctime),
                "modified_at": _timestamp_iso(stat.st_mtime),
                "last_seen_at": now,
                "processing_status": "discovered",
                "error_message": None,
            }
            upserted = _upsert_file(conn, vault_id=vault_id, record=record)
            if upserted:
                discovered_count += 1
        conn.commit()
    return ProcessSummary(discovered_count=discovered_count)


def hash_discovered_files(vault_path: Path) -> ProcessSummary:
    queued_count = 0
    skipped_count = 0
    pending_image_count = 0

    with connect_database(vault_path) as conn:
        file_rows = conn.execute(
            """
            SELECT id, path, relative_path, file_type, sha256, processing_status
            FROM files
            WHERE vault_id = ?
            """,
            (_vault_id(vault_path),),
        ).fetchall()

        for row in file_rows:
            file_path = Path(row["path"])
            if not file_path.exists() or not file_path.is_file():
                continue

            new_hash = _sha256_file(file_path)
            previous_hash = row["sha256"] or ""
            unchanged = bool(previous_hash) and previous_hash == new_hash

            next_status = row["processing_status"]
            if row["file_type"] == "image":
                next_status = "pending_image"
                pending_image_count += 1
            elif row["file_type"] == "unsupported":
                next_status = "unsupported"
            elif unchanged and row["processing_status"] in {"processed", "skipped_unchanged", "extraction_limited"}:
                next_status = "skipped_unchanged"
                skipped_count += 1
            else:
                next_status = "queued"
                queued_count += 1

            conn.execute(
                """
                UPDATE files
                SET sha256 = ?, processing_status = ?, error_message = NULL, modified_at = ?, size_bytes = ?, last_seen_at = ?
                WHERE id = ?
                """,
                (
                    new_hash,
                    next_status,
                    _timestamp_iso(file_path.stat().st_mtime),
                    int(file_path.stat().st_size),
                    _now_iso(),
                    row["id"],
                ),
            )

        conn.commit()

    return ProcessSummary(
        queued_count=queued_count,
        skipped_count=skipped_count,
        pending_image_count=pending_image_count,
    )


def process_queued_files(vault_path: Path) -> ProcessSummary:
    processed_count = 0
    failed_count = 0
    pending_image_count = 0

    with connect_database(vault_path) as conn:
        rows = conn.execute(
            """
            SELECT id, path, relative_path, file_type, processing_status
            FROM files
            WHERE vault_id = ? AND processing_status IN ('queued', 'processing')
            ORDER BY relative_path ASC
            """,
            (_vault_id(vault_path),),
        ).fetchall()

        for row in rows:
            file_id = row["id"]
            file_path = Path(row["path"])

            if not file_path.exists() or not file_path.is_file():
                conn.execute(
                    "UPDATE files SET processing_status = 'failed_permanent', error_message = ? WHERE id = ?",
                    ("Source file missing during processing.", file_id),
                )
                failed_count += 1
                continue

            if row["file_type"] == "image":
                conn.execute(
                    "UPDATE files SET processing_status = 'pending_image', last_processed_at = ?, error_message = NULL WHERE id = ?",
                    (_now_iso(), file_id),
                )
                pending_image_count += 1
                continue

            if row["file_type"] == "unsupported":
                conn.execute(
                    "UPDATE files SET processing_status = 'unsupported', last_processed_at = ?, error_message = NULL WHERE id = ?",
                    (_now_iso(), file_id),
                )
                continue

            conn.execute("UPDATE files SET processing_status = 'processing', error_message = NULL WHERE id = ?", (file_id,))

            try:
                extraction = extract_file(file_path, row["file_type"])
                if extraction is None:
                    raise ValueError("Unsupported file type for extraction")

                extraction_id = _upsert_extraction(
                    conn,
                    file_id=file_id,
                    title=extraction.title,
                    extracted_text=extraction.text,
                    metadata=extraction.metadata,
                )
                _replace_chunks(
                    conn,
                    file_id=file_id,
                    extraction_id=extraction_id,
                    relative_path=row["relative_path"],
                    chunks=extraction.chunks,
                )

                status = "extraction_limited" if extraction.limited else "processed"
                conn.execute(
                    """
                    UPDATE files
                    SET processing_status = ?, last_processed_at = ?, error_message = NULL
                    WHERE id = ?
                    """,
                    (status, _now_iso(), file_id),
                )
                if extraction.limited:
                    failed_count += 1
                else:
                    processed_count += 1
            except Exception as exc:
                conn.execute(
                    "UPDATE files SET processing_status = 'failed_transient', error_message = ? WHERE id = ?",
                    (str(exc), file_id),
                )
                failed_count += 1

        conn.commit()

    return ProcessSummary(
        processed_count=processed_count,
        failed_count=failed_count,
        pending_image_count=pending_image_count,
    )


def ingest_raw_files(vault_path: Path) -> ProcessSummary:
    scan = scan_raw_files(vault_path)
    hashed = hash_discovered_files(vault_path)
    processed = process_queued_files(vault_path)
    return ProcessSummary(
        discovered_count=scan.discovered_count,
        queued_count=hashed.queued_count,
        skipped_count=hashed.skipped_count,
        pending_image_count=hashed.pending_image_count + processed.pending_image_count,
        processed_count=processed.processed_count,
        failed_count=processed.failed_count,
    )


def list_raw_inbox(vault_path: Path) -> list[FileSnapshot]:
    with connect_database(vault_path) as conn:
        rows = conn.execute(
            """
            SELECT path, relative_path, file_type, size_bytes, modified_at, created_at, processing_status, error_message, sha256
            FROM files
            WHERE vault_id = ?
            ORDER BY relative_path ASC
            """,
            (_vault_id(vault_path),),
        ).fetchall()

    return [
        FileSnapshot(
            path=row["path"],
            relative_path=row["relative_path"],
            file_type=row["file_type"],
            size_bytes=int(row["size_bytes"] or 0),
            modified_at=row["modified_at"] or "",
            created_at=row["created_at"] or "",
            processing_status=row["processing_status"],
            error_message=row["error_message"],
            sha256=row["sha256"] or "",
        )
        for row in rows
    ]


def process_single_path(vault_path: Path, file_path: Path) -> ProcessSummary:
    if not file_path.exists() or not file_path.is_file():
        return ProcessSummary()

    raw_root = vault_path / "Raw"
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(raw_root.resolve())):
        return ProcessSummary()

    relative = resolved.relative_to(vault_path)
    if _is_protected_relative(relative):
        return ProcessSummary()

    with connect_database(vault_path) as conn:
        vault_id = _ensure_vault_row(conn, vault_path)
        stat = resolved.stat()
        file_type = supported_file_type(resolved)
        record = {
            "path": str(resolved),
            "relative_path": relative.as_posix(),
            "file_type": file_type,
            "size_bytes": int(stat.st_size),
            "created_at": _timestamp_iso(stat.st_ctime),
            "modified_at": _timestamp_iso(stat.st_mtime),
            "last_seen_at": _now_iso(),
            "processing_status": "discovered",
            "error_message": None,
        }
        _upsert_file(conn, vault_id=vault_id, record=record)
        conn.commit()

    hashed = hash_discovered_files(vault_path)
    processed = process_queued_files(vault_path)
    return ProcessSummary(
        queued_count=hashed.queued_count,
        skipped_count=hashed.skipped_count,
        processed_count=processed.processed_count,
        failed_count=processed.failed_count,
        pending_image_count=hashed.pending_image_count + processed.pending_image_count,
    )


def asdict_files(files: list[FileSnapshot]) -> list[dict[str, object]]:
    return [asdict(item) for item in files]


def _vault_id(vault_path: Path) -> str:
    return hashlib.sha256(str(vault_path.resolve()).encode("utf-8")).hexdigest()


def _ensure_vault_row(conn, vault_path: Path) -> str:
    vault_id = _vault_id(vault_path)
    existing = conn.execute("SELECT id FROM vaults WHERE id = ?", (vault_id,)).fetchone()
    now = _now_iso()
    if existing:
        conn.execute("UPDATE vaults SET last_opened_at = ? WHERE id = ?", (now, vault_id))
        return vault_id

    conn.execute(
        "INSERT INTO vaults(id, path, created_at, last_opened_at) VALUES(?, ?, ?, ?)",
        (vault_id, str(vault_path), now, now),
    )
    return vault_id


def _upsert_file(conn, vault_id: str, record: dict[str, object]) -> bool:
    row = conn.execute(
        "SELECT id, processing_status FROM files WHERE vault_id = ? AND relative_path = ? LIMIT 1",
        (vault_id, record["relative_path"]),
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
                vault_id,
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


def _upsert_extraction(conn, file_id: str, title: str | None, extracted_text: str, metadata: dict[str, object]) -> str:
    now = _now_iso()
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


def _replace_chunks(conn, file_id: str, extraction_id: str, relative_path: str, chunks) -> None:
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
                _approx_token_count(chunk.text),
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


def _iter_raw_files(vault_path: Path):
    raw_root = vault_path / "Raw"
    if not raw_root.exists() or not raw_root.is_dir():
        return
    for candidate in raw_root.rglob("*"):
        if not candidate.is_file():
            continue
        yield candidate


def _is_protected_relative(relative_path: Path) -> bool:
    parts = [part.lower() for part in relative_path.parts]
    return any(part in PROTECTED_FOLDERS for part in parts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _approx_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp_iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat()
