from pathlib import Path

from llm_wiki.core.config import AppConfig
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
from llm_wiki.ui.dashboard import build_dashboard_data, render_dashboard_text


def test_dashboard_shows_counts_recent_generated_and_errors(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    file_a = tmp_path / "a.md"
    file_b = tmp_path / "b.txt"
    file_c = tmp_path / "c.md"
    file_a.write_text("# A", encoding="utf-8")
    file_b.write_text("B", encoding="utf-8")
    file_c.write_text("# C", encoding="utf-8")

    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, tmp_path)
        scanned_a = ScannedFile(path=file_a, relative_path=Path("a.md"), extension=".md", size_bytes=file_a.stat().st_size)
        scanned_b = ScannedFile(path=file_b, relative_path=Path("b.txt"), extension=".txt", size_bytes=file_b.stat().st_size)
        scanned_c = ScannedFile(path=file_c, relative_path=Path("c.md"), extension=".md", size_bytes=file_c.stat().st_size)
        id_a = upsert_scanned_file(connection, vault_id, scanned_a, sha256="sha-a")
        id_b = upsert_scanned_file(connection, vault_id, scanned_b, sha256="sha-b")
        id_c = upsert_scanned_file(connection, vault_id, scanned_c, sha256="sha-c")

        set_file_status(connection, id_a, FILE_STATUS_GENERATED)
        set_file_status(connection, id_b, FILE_STATUS_PROCESSING)
        set_file_status(connection, id_c, FILE_STATUS_FAILED_PERMANENT, "parse failed")

        data = build_dashboard_data(
            connection=connection,
            config=AppConfig(provider="groq", groq_api_key="x", model="m1"),
            vault_root=tmp_path,
        )

    assert data.raw_sources_found == 3
    assert data.processed_count == 1
    assert data.queued_or_processing_count == 1
    assert data.provider_status == "configured"
    assert len(data.recent_generated) == 1
    assert data.recent_generated[0].relative_path == "a.md"
    assert len(data.recent_error_items) == 1
    assert data.recent_error_items[0].relative_path == "c.md"
    assert data.recent_error_items[0].error_message == "parse failed"

    rendered = render_dashboard_text(data)
    assert "Raw sources found: 3" in rendered
    assert "Processed: 1" in rendered
    assert "Queued/Processing: 1" in rendered
    assert "Recent generated files:" in rendered
    assert "a.md [generated]" in rendered
    assert "Recent errors:" in rendered
    assert "c.md [failed_permanent] parse failed" in rendered
