from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.ingestion.extractors import extract_file, supported_file_type
from llm_wiki_backend.ingestion.fs_utils import (
    PROTECTED_FOLDERS,
    is_protected_relative,
    iter_raw_files,
    sha256_file,
)
from llm_wiki_backend.ingestion.repository import (
    ensure_vault_row,
    replace_chunks,
    upsert_extraction,
    upsert_file,
    vault_id,
)
from llm_wiki_backend.ingestion.time_utils import now_iso, timestamp_iso
from llm_wiki_backend.ingestion.types import FileSnapshot, ProcessSummary
from llm_wiki_backend.wiki.service import generate_wiki_for_pending_sources


def scan_raw_files(vault_path: Path) -> ProcessSummary:
    discovered_count = 0
    with connect_database(vault_path) as conn:
        vault_id_value = ensure_vault_row(conn, vault_path)
        for file_path in iter_raw_files(vault_path):
            relative = file_path.relative_to(vault_path)
            if is_protected_relative(relative):
                continue
            file_type = supported_file_type(file_path)
            stat = file_path.stat()
            record = {
                "path": str(file_path),
                "relative_path": relative.as_posix(),
                "file_type": file_type,
                "size_bytes": int(stat.st_size),
                "created_at": timestamp_iso(stat.st_ctime),
                "modified_at": timestamp_iso(stat.st_mtime),
                "last_seen_at": now_iso(),
                "processing_status": "discovered",
                "error_message": None,
            }
            upserted = upsert_file(conn, vault_id_value=vault_id_value, record=record)
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
            (vault_id(vault_path),),
        ).fetchall()

        for row in file_rows:
            file_path = Path(row["path"])
            if not file_path.exists() or not file_path.is_file():
                continue

            new_hash = sha256_file(file_path)
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
                    timestamp_iso(file_path.stat().st_mtime),
                    int(file_path.stat().st_size),
                    now_iso(),
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
            (vault_id(vault_path),),
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
                    (now_iso(), file_id),
                )
                pending_image_count += 1
                continue

            if row["file_type"] == "unsupported":
                conn.execute(
                    "UPDATE files SET processing_status = 'unsupported', last_processed_at = ?, error_message = NULL WHERE id = ?",
                    (now_iso(), file_id),
                )
                continue

            conn.execute("UPDATE files SET processing_status = 'processing', error_message = NULL WHERE id = ?", (file_id,))

            try:
                extraction = extract_file(file_path, row["file_type"])
                if extraction is None:
                    raise ValueError("Unsupported file type for extraction")

                extraction_id = upsert_extraction(
                    conn,
                    file_id=file_id,
                    title=extraction.title,
                    extracted_text=extraction.text,
                    metadata=extraction.metadata,
                )
                replace_chunks(
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
                    (status, now_iso(), file_id),
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
    wiki_summary = generate_wiki_for_pending_sources(vault_path)
    return ProcessSummary(
        discovered_count=scan.discovered_count,
        queued_count=hashed.queued_count,
        skipped_count=hashed.skipped_count,
        pending_image_count=hashed.pending_image_count + processed.pending_image_count,
        processed_count=processed.processed_count,
        failed_count=processed.failed_count + wiki_summary.failed_count,
        wiki_generation=wiki_summary.model_dump(),
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
            (vault_id(vault_path),),
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
    if is_protected_relative(relative):
        return ProcessSummary()

    with connect_database(vault_path) as conn:
        vault_id_value = ensure_vault_row(conn, vault_path)
        stat = resolved.stat()
        file_type = supported_file_type(resolved)
        record = {
            "path": str(resolved),
            "relative_path": relative.as_posix(),
            "file_type": file_type,
            "size_bytes": int(stat.st_size),
            "created_at": timestamp_iso(stat.st_ctime),
            "modified_at": timestamp_iso(stat.st_mtime),
            "last_seen_at": now_iso(),
            "processing_status": "discovered",
            "error_message": None,
        }
        upsert_file(conn, vault_id_value=vault_id_value, record=record)
        conn.commit()

    hashed = hash_discovered_files(vault_path)
    processed = process_queued_files(vault_path)
    wiki_summary = generate_wiki_for_pending_sources(vault_path)
    return ProcessSummary(
        queued_count=hashed.queued_count,
        skipped_count=hashed.skipped_count,
        processed_count=processed.processed_count,
        failed_count=processed.failed_count + wiki_summary.failed_count,
        pending_image_count=hashed.pending_image_count + processed.pending_image_count,
        wiki_generation=wiki_summary.model_dump(),
    )


def asdict_files(files: list[FileSnapshot]) -> list[dict[str, object]]:
    return [asdict(item) for item in files]
