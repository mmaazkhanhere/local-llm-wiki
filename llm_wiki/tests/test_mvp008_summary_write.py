from pathlib import Path

from llm_wiki.app import process_markdown_or_text_if_supported, sha256_file
from llm_wiki.core.config import AppConfig
from llm_wiki.core.database import (
    Database,
    FILE_STATUS_DISCOVERED,
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
        return "## Key Ideas\n- Idea A\n- Idea B"


def test_summary_file_written_to_llm_wiki_sources(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    raw = tmp_path / "raw.md"
    original = "# Source Title\nRaw body."
    raw.write_text(original, encoding="utf-8")
    scanned = ScannedFile(
        path=raw,
        relative_path=Path("raw.md"),
        extension=".md",
        size_bytes=raw.stat().st_size,
    )

    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, tmp_path)
        file_id = upsert_scanned_file(
            connection=connection,
            vault_id=vault_id,
            scanned=scanned,
            sha256=sha256_file(raw),
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

        page_row = connection.execute(
            "SELECT relative_path, status FROM generated_pages WHERE page_type = 'source_summary'",
        ).fetchone()
        assert page_row is not None
        assert page_row["relative_path"].startswith("LLM Wiki/Sources/")
        assert page_row["status"] == "generated"
        audit_row = connection.execute(
            "SELECT event_type, target_path FROM audit_log ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        assert audit_row is not None
        assert audit_row["event_type"] == "generated_summary_written"
        assert audit_row["target_path"].startswith("LLM Wiki/Sources/")

    summary_files = list(layout.sources_dir.glob("*.md"))
    assert len(summary_files) == 1
    summary_text = summary_files[0].read_text(encoding="utf-8")
    assert "# Source Title Summary" in summary_text
    assert "## Key Ideas" in summary_text
    assert "Source: `raw.md`" in summary_text
    assert "Source Summaries" in layout.index_file.read_text(encoding="utf-8")
    assert "Source Title summary" in layout.index_file.read_text(encoding="utf-8")
    processing_log = layout.processing_log_file.read_text(encoding="utf-8")
    assert "Processed source: `raw.md`" in processing_log
    assert "Status: Auto-generated" in processing_log
    audit_jsonl = (layout.audit_dir / "audit-log.jsonl").read_text(encoding="utf-8")
    assert '"event_type": "generated_summary_written"' in audit_jsonl
    assert '"source_path": "raw.md"' in audit_jsonl

    # Raw note must remain unchanged.
    assert raw.read_text(encoding="utf-8") == original
