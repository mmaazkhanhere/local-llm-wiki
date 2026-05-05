from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm_wiki_backend.main import app
from llm_wiki_backend.wiki.service import parse_candidate_response

client = TestClient(app)


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


def test_candidate_parser_rejects_invalid_llm_payload() -> None:
    invalid_payload = json.dumps(
        {
            "concepts": [{"summary": "Missing title"}],
            "entities": [],
            "comparisons": [],
            "maps": [],
            "flashcards": [],
        }
    )

    with pytest.raises(ValueError):
        parse_candidate_response(invalid_payload)


def test_phase3_generates_wiki_pages_flashcards_index_and_log(
    vault_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap(vault_path)
    raw_note = vault_path / "Raw" / "transformers.md"
    raw_note.write_text(
        "# Transformers\n\nTransformers use self-attention to model token relationships.\n",
        encoding="utf-8",
    )

    existing_page = vault_path / "Wiki" / "Concepts" / "Transformer.md"
    existing_page.write_text("# Transformer\n\nExisting content must stay untouched.\n", encoding="utf-8")

    mocked_response = json.dumps(
        {
            "concepts": [
                {
                    "title": "Self-Attention",
                    "summary": "Mechanism for weighting relevant tokens during sequence modeling.",
                    "body": [
                        "Self-attention lets a model compare each token with other tokens in the same context.",
                        "It is a core building block in [[Transformer]].",
                    ],
                    "links": ["Transformer"],
                    "source_notes": ['section "Transformers"'],
                }
            ],
            "entities": [
                {
                    "title": "Transformer",
                    "summary": "Neural network architecture built around attention.",
                    "body": [
                        "Transformers replace recurrence with attention-driven context mixing."
                    ],
                    "links": ["Self-Attention"],
                    "source_notes": ['section "Transformers"'],
                }
            ],
            "comparisons": [
                {
                    "title": "Transformer vs RNN",
                    "summary": "Contrast between attention-first and recurrence-first sequence models.",
                    "body": [
                        "| Aspect | Transformer | RNN |",
                        "| --- | --- | --- |",
                        "| Core mechanism | Attention | Recurrence |",
                    ],
                    "links": ["Transformer", "Self-Attention"],
                    "source_notes": ['section "Transformers"'],
                }
            ],
            "maps": [
                {
                    "title": "Transformer Learning Map",
                    "summary": "Suggested order for learning the main Transformer ideas.",
                    "body": [
                        "- [[Transformer]]",
                        "- [[Self-Attention]]",
                        "- [[Transformer vs RNN]]",
                    ],
                    "links": ["Transformer", "Self-Attention", "Transformer vs RNN"],
                    "source_notes": ['section "Transformers"'],
                }
            ],
            "flashcards": [
                {
                    "title": "Transformer Basics",
                    "question": "What problem does self-attention solve inside a Transformer?",
                    "answer": "It helps each token weigh other relevant tokens in the same sequence.",
                    "related_pages": ["Self-Attention", "Transformer"],
                    "source_notes": ['section "Transformers"'],
                }
            ],
        }
    )

    monkeypatch.setattr(
        "llm_wiki_backend.wiki.service.generate_candidate_response",
        lambda **_: mocked_response,
    )

    run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert run.status_code == 200
    wiki_generation = run.json()["wiki_generation"]
    assert wiki_generation["sources_processed_count"] == 1
    assert wiki_generation["pages_created_count"] == 4
    assert wiki_generation["flashcard_files_created_count"] == 1
    assert wiki_generation["failed_count"] == 0
    assert wiki_generation["sources"][0]["status"] == "generated"
    assert wiki_generation["sources"][0]["candidates"]["concepts"] == ["Self-Attention"]

    concept_page = vault_path / "Wiki" / "Concepts" / "Self-Attention.md"
    entity_page = vault_path / "Wiki" / "Entities" / "Transformer.md"
    comparison_page = vault_path / "Wiki" / "Comparisons" / "Transformer vs RNN.md"
    map_page = vault_path / "Wiki" / "Maps" / "Transformer Learning Map.md"
    flashcards_page = vault_path / "Wiki" / "Flashcards" / "Transformer Basics.md"

    assert concept_page.is_file()
    assert entity_page.is_file()
    assert comparison_page.is_file()
    assert map_page.is_file()
    assert flashcards_page.is_file()

    concept_text = concept_page.read_text(encoding="utf-8")
    assert "# Self-Attention" in concept_text
    assert "[[Transformer]]" in concept_text
    assert "## Claims and Provenance" in concept_text
    assert "Source: `Raw/transformers.md`" in concept_text
    assert "## Sources" in concept_text
    assert "`Raw/transformers.md`" in concept_text

    entity_text = entity_page.read_text(encoding="utf-8")
    assert "# Transformer" in entity_text
    assert existing_page.read_text(encoding="utf-8") == "# Transformer\n\nExisting content must stay untouched.\n"

    index_text = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8")
    assert "[[Self-Attention]] - Mechanism for weighting relevant tokens during sequence modeling." in index_text
    assert "[[Transformer]] - Neural network architecture built around attention." in index_text
    assert "[[Transformer vs RNN]] - Contrast between attention-first and recurrence-first sequence models." in index_text
    assert "[[Transformer Learning Map]] - Suggested order for learning the main Transformer ideas." in index_text

    log_text = (vault_path / "Wiki" / "log.md").read_text(encoding="utf-8")
    assert "`Raw/transformers.md`" in log_text
    assert "Self-Attention" in log_text
    assert "Transformer Basics" in log_text

    db_path = vault_path / ".llm-wiki" / "app.db"
    with sqlite3.connect(db_path) as conn:
        wiki_page_count = conn.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
        flashcard_count = conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0]
        audit_count = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert wiki_page_count == 4
    assert flashcard_count == 1
    assert audit_count >= 3


def test_phase3_normalizes_titles_for_paths_and_index_links(
    vault_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap(vault_path)
    raw_note = vault_path / "Raw" / "hooks.md"
    raw_note.write_text("# Hooks\n\nhook payload details", encoding="utf-8")

    mocked_response = json.dumps(
        {
            "concepts": [
                {
                    "title": ".claude/settings.json",
                    "summary": "Configuration for hook execution and routing behavior in Claude.",
                    "body": [
                        "The file defines hook execution targets and payload routing.",
                        "Changes here affect operational automation behavior.",
                    ],
                    "links": ["Hook Execution"],
                    "source_notes": ['section "Beyond Command Hooks"'],
                    "why_it_matters": "It controls practical command automation behavior.",
                    "how_it_works": ["Hook event payloads are routed based on configured rules."],
                    "examples": ["POST payload to a local endpoint for processing automation."],
                    "use_cases": ["Enforce command safety policy in local workflows."],
                    "failure_modes": ["Bad routing config can break hook execution."],
                }
            ],
            "entities": [],
            "comparisons": [],
            "maps": [],
            "flashcards": [],
        }
    )
    monkeypatch.setattr(
        "llm_wiki_backend.wiki.service.generate_candidate_response",
        lambda **_: mocked_response,
    )

    run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert run.status_code == 200

    concept_page = vault_path / "Wiki" / "Concepts" / ".claude settings.json.md"
    assert concept_page.is_file()
    concept_text = concept_page.read_text(encoding="utf-8")
    assert "# .claude settings.json" in concept_text

    index_text = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8")
    assert "[[.claude settings.json]] - Configuration for hook execution and routing behavior in Claude." in index_text
