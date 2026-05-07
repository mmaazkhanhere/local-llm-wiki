from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm_wiki_backend.main import app
from llm_wiki_backend.wiki.models import parse_generation_plan

client = TestClient(app)


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload

    def complete_structured(self, *, system_prompt: str, user_prompt: str, schema: dict):
        return self.payload


@pytest.fixture
def vault_path() -> Path:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"vault-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(path, ignore_errors=True)


def _bootstrap(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200


def test_generation_plan_parser_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError):
        parse_generation_plan('{"candidates": [{"page_type": "concept", "title": "Bad"}]}')


def test_phase3_generates_pages_flashcards_index_and_log(vault_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap(vault_path)
    monkeypatch.setattr(
        "llm_wiki_backend.wiki.service.get_wiki_llm_provider",
        lambda vault: FakeProvider(
            {
                "candidates": [
                    {
                        "page_type": "concept",
                        "title": "Attention Mechanism",
                        "summary": "How a model focuses on relevant tokens.",
                        "content_markdown": "Attention scores weight which tokens matter most during computation.",
                        "wiki_links": ["Transformer"],
                        "sources": [{"locator": 'section "Attention"'}],
                    },
                    {
                        "page_type": "entity",
                        "title": "Transformer",
                        "summary": "A neural network architecture built around attention.",
                        "content_markdown": "Transformers stack attention and feed-forward blocks.",
                        "wiki_links": ["Attention Mechanism"],
                        "sources": [{"locator": 'section "Architecture"'}],
                    },
                    {
                        "page_type": "comparison",
                        "title": "RNN vs Transformer",
                        "summary": "Tradeoffs between sequential recurrence and attention-first modeling.",
                        "content_markdown": "| Model | Strength |\n| --- | --- |\n| RNN | Sequential state |\n| Transformer | Parallel attention |",
                        "wiki_links": ["Transformer"],
                        "sources": [{"locator": 'section "Comparison"'}],
                    },
                    {
                        "page_type": "map",
                        "title": "Transformer Learning Map",
                        "summary": "A short study path for transformer topics.",
                        "content_markdown": "- [[Attention Mechanism]]\n- [[Transformer]]\n- [[RNN vs Transformer]]",
                        "wiki_links": ["Attention Mechanism", "Transformer"],
                        "sources": [{"locator": 'section "Study Plan"'}],
                    },
                ],
                "flashcards": [
                    {
                        "question": "What does attention do?",
                        "answer": "It assigns weights to relevant tokens before combining information.",
                        "sources": [{"locator": 'section "Attention"'}],
                    }
                ],
            }
        ),
    )

    raw_source = vault_path / "Raw" / "transformers.md"
    raw_source.write_text(
        "# Transformers\n\n## Attention\n\nAttention weights relevant tokens.\n\n## Architecture\n\nTransformers stack attention blocks.",
        encoding="utf-8",
    )

    response = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert response.status_code == 200
    payload = response.json()
    assert payload["wiki_generation"]["generated_page_count"] == 4
    assert payload["wiki_generation"]["generated_flashcard_count"] == 1
    assert payload["wiki_generation"]["failed_count"] == 0

    concept_page = vault_path / "Wiki" / "Concepts" / "Attention Mechanism.md"
    entity_page = vault_path / "Wiki" / "Entities" / "Transformer.md"
    comparison_page = vault_path / "Wiki" / "Comparisons" / "RNN vs Transformer.md"
    map_page = vault_path / "Wiki" / "Maps" / "Transformer Learning Map.md"
    flashcard_page = vault_path / "Wiki" / "Flashcards" / "transformers.md"

    assert concept_page.is_file()
    assert entity_page.is_file()
    assert comparison_page.is_file()
    assert map_page.is_file()
    assert flashcard_page.is_file()

    assert "## Sources" in concept_page.read_text(encoding="utf-8")
    assert "[[Transformer]]" in concept_page.read_text(encoding="utf-8")

    index_content = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8")
    assert "- [[Attention Mechanism]] — How a model focuses on relevant tokens." in index_content
    assert "- [[Transformer]] — A neural network architecture built around attention." in index_content

    log_content = (vault_path / "Wiki" / "log.md").read_text(encoding="utf-8")
    assert "source=`Raw/transformers.md`" in log_content
    assert "Wiki/Concepts/Attention Mechanism.md" in log_content

    second_run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert second_run.status_code == 200
    second_payload = second_run.json()
    assert second_payload["wiki_generation"]["generated_page_count"] == 0


def test_phase3_invalid_llm_output_fails_safely(vault_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap(vault_path)
    monkeypatch.setattr(
        "llm_wiki_backend.wiki.service.get_wiki_llm_provider",
        lambda vault: FakeProvider({"candidates": [{"page_type": "concept", "title": "Broken"}], "flashcards": []}),
    )
    (vault_path / "Raw" / "broken.md").write_text("# Broken\n\nbad", encoding="utf-8")

    response = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert response.status_code == 200
    payload = response.json()
    assert payload["wiki_generation"]["failed_count"] == 1
    assert payload["wiki_generation"]["source_results"][0]["status"] == "failed"
    assert not (vault_path / "Wiki" / "Concepts" / "Broken.md").exists()
