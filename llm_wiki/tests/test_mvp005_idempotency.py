from pathlib import Path

from llm_wiki.app import sha256_file
from llm_wiki.core.database import (
    Database,
    FILE_STATUS_DISCOVERED,
    FILE_STATUS_SKIPPED_UNCHANGED,
    get_file_by_relative_path,
    initialize_schema,
    upsert_scanned_file,
    upsert_vault,
)
from llm_wiki.core.scanner import ScannedFile
from llm_wiki.core.vault import initialize_vault


def test_unchanged_hash_marks_skipped(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    source_path = tmp_path / "note.md"
    source_path.write_text("# Title\nbody", encoding="utf-8")
    scanned = ScannedFile(
        path=source_path,
        relative_path=Path("note.md"),
        extension=".md",
        size_bytes=source_path.stat().st_size,
    )
    digest = sha256_file(source_path)

    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, tmp_path)
        upsert_scanned_file(
            connection,
            vault_id=vault_id,
            scanned=scanned,
            sha256=digest,
            status=FILE_STATUS_DISCOVERED,
        )
        row = get_file_by_relative_path(connection, vault_id, "note.md")
        assert row is not None
        assert row["sha256"] == digest

        upsert_scanned_file(
            connection,
            vault_id=vault_id,
            scanned=scanned,
            sha256=digest,
            status=FILE_STATUS_SKIPPED_UNCHANGED,
        )
        row2 = get_file_by_relative_path(connection, vault_id, "note.md")
        assert row2 is not None
        assert row2["processing_status"] == FILE_STATUS_SKIPPED_UNCHANGED
