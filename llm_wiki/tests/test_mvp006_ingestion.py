from pathlib import Path

from llm_wiki.app import process_markdown_or_text_if_supported, sha256_file
from llm_wiki.core.config import AppConfig
from llm_wiki.core.database import (
    Database,
    FILE_STATUS_DISCOVERED,
    FILE_STATUS_GENERATED,
    initialize_schema,
    upsert_scanned_file,
    upsert_vault,
)
from llm_wiki.core.scanner import ScannedFile
from llm_wiki.core.vault import initialize_vault


class _FakeProvider:
    def provider_name(self) -> str:
        return "fake"

    def generate_text(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> str:
        return "## Overview\nA test summary."


def test_markdown_ingestion_persists_source_and_chunks(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    source_path = tmp_path / "lesson.md"
    source_path.write_text("# Linear Algebra\nThis is a test note for chunking.", encoding="utf-8")
    scanned = ScannedFile(
        path=source_path,
        relative_path=Path("lesson.md"),
        extension=".md",
        size_bytes=source_path.stat().st_size,
    )

    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, tmp_path)
        file_id = upsert_scanned_file(
            connection,
            vault_id=vault_id,
            scanned=scanned,
            sha256=sha256_file(source_path),
            status=FILE_STATUS_DISCOVERED,
        )
        process_markdown_or_text_if_supported(
            connection=connection,
            file_id=file_id,
            scanned_file=scanned,
            provider=_FakeProvider(),
            config=AppConfig(model="test-model"),
            vault_root=tmp_path,
        )

        file_row = connection.execute(
            "SELECT processing_status FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
        assert file_row is not None
        assert file_row["processing_status"] == FILE_STATUS_GENERATED

        source_row = connection.execute(
            "SELECT id, title, extracted_text FROM source_documents WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        assert source_row is not None
        assert source_row["title"] == "Linear Algebra"
        assert "chunking" in source_row["extracted_text"]

        chunk_rows = connection.execute(
            "SELECT chunk_index, text FROM chunks WHERE source_document_id = ? ORDER BY chunk_index ASC",
            (source_row["id"],),
        ).fetchall()
        assert len(chunk_rows) >= 1
        assert chunk_rows[0]["chunk_index"] == 0
        assert len(chunk_rows[0]["text"]) > 0


def test_text_ingestion_uses_first_nonempty_line_as_title(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    source_path = tmp_path / "plain.txt"
    source_path.write_text("\n\nMy Text Title\nBody paragraph.", encoding="utf-8")
    scanned = ScannedFile(
        path=source_path,
        relative_path=Path("plain.txt"),
        extension=".txt",
        size_bytes=source_path.stat().st_size,
    )

    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, tmp_path)
        file_id = upsert_scanned_file(
            connection,
            vault_id=vault_id,
            scanned=scanned,
            sha256=sha256_file(source_path),
            status=FILE_STATUS_DISCOVERED,
        )
        process_markdown_or_text_if_supported(
            connection=connection,
            file_id=file_id,
            scanned_file=scanned,
            provider=_FakeProvider(),
            config=AppConfig(model="test-model"),
            vault_root=tmp_path,
        )
        source_row = connection.execute(
            "SELECT title FROM source_documents WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        assert source_row is not None
        assert source_row["title"] == "My Text Title"
