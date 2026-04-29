from pathlib import Path

from llm_wiki.core.database import (
    Database,
    FILE_STATUS_FAILED_PERMANENT,
    FILE_STATUS_GENERATED,
    FILE_STATUS_PROCESSING,
    initialize_schema,
    set_file_status,
    upsert_scanned_file,
    upsert_vault,
)
from llm_wiki.core.scanner import ScannedFile
from llm_wiki.core.vault import initialize_vault


def test_schema_initializes_all_mvp_tables(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    required = {"vaults", "files", "source_documents", "chunks", "generated_pages", "audit_log"}
    assert required.issubset(names)


def test_file_status_transitions_are_persisted(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    db = Database(layout.db_path)
    source = tmp_path / "note.md"
    source.write_text("# n", encoding="utf-8")
    scanned = ScannedFile(
        path=source,
        relative_path=Path("note.md"),
        extension=".md",
        size_bytes=source.stat().st_size,
    )

    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, tmp_path)
        file_id = upsert_scanned_file(connection, vault_id, scanned, sha256="abc", status=FILE_STATUS_PROCESSING)
        set_file_status(connection, file_id, FILE_STATUS_GENERATED)
        set_file_status(connection, file_id, FILE_STATUS_FAILED_PERMANENT, "parser error")
        row = connection.execute(
            "SELECT processing_status, error_message, last_processed_at FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()

    assert row["processing_status"] == FILE_STATUS_FAILED_PERMANENT
    assert row["error_message"] == "parser error"
    assert row["last_processed_at"] is not None
