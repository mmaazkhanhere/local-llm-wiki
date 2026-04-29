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
from llm_wiki.retrieval.qa import answer_question


class _FakeProvider:
    def provider_name(self) -> str:
        return "fake"

    def generate_text(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> str:
        return "## Key Ideas\n- Gradient descent reduces loss."


def test_ask_returns_grounded_supported_answer(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    raw = tmp_path / "ml.md"
    raw.write_text("# Training\nGradient descent updates model weights.", encoding="utf-8")
    scanned = ScannedFile(
        path=raw,
        relative_path=Path("ml.md"),
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
        result = answer_question(connection, tmp_path, "How does gradient descent work?")

    assert result.supported is True
    assert "Grounded answer based on retrieved sources" in result.answer
    assert any("chunk" in citation or "LLM Wiki/Sources/" in citation for citation in result.citations)


def test_ask_returns_not_supported_when_no_hits(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        upsert_vault(connection, tmp_path)
        result = answer_question(connection, tmp_path, "What is the capital of Mars?")
    assert result.supported is False
    assert result.answer == "Not supported by the current sources."
    assert result.citations == []
