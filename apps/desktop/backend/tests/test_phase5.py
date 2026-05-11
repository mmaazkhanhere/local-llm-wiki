from __future__ import annotations

import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from llm_wiki_backend.main import app

client = TestClient(app)


class FakeAskProvider:
    def __init__(self, payload: dict):
        self._payload = payload

    def complete_structured(self, *, system_prompt: str, user_prompt: str, schema: dict):
        return self._payload


def _bootstrap(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200


def _connect_db(vault_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(vault_path / ".llm-wiki" / "app.db")
    conn.row_factory = sqlite3.Row
    return conn


def _seed_wiki_page(vault_path: Path, *, title: str, relative_path: str, content: str) -> None:
    page_path = vault_path / relative_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(content, encoding="utf-8")
    with _connect_db(vault_path) as conn:
        page_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO wiki_pages(id, extraction_id, page_type, path, relative_path, sha256, title, summary, created_at, updated_at, status)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                page_id,
                None,
                "concept",
                str(page_path),
                relative_path,
                "seed",
                title,
                "seed summary",
                now,
                now,
                "generated",
            ),
        )
        conn.execute(
            """
            INSERT INTO wiki_pages_fts(wiki_page_id, relative_path, title, summary, content)
            VALUES(?, ?, ?, ?, ?)
            """,
            (page_id, relative_path, title, "seed summary", content),
        )
        conn.commit()


def _seed_raw_chunk(vault_path: Path, *, relative_path: str, text: str, heading: str | None = None) -> None:
    with _connect_db(vault_path) as conn:
        conn.execute(
            """
            INSERT INTO chunks_fts(chunk_id, extraction_id, file_id, relative_path, text, heading, page_number, line_start, line_end)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), relative_path, text, heading, 1, 1, 4),
        )
        conn.commit()


def test_phase5_query_prefers_wiki_and_does_not_write(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        content = "# Attention Mechanism\n\nAttention uses weights.\n\n## Related\n\n- [[Transformer]]\n"
        _seed_wiki_page(
            vault_path,
            title="Attention Mechanism",
            relative_path="Wiki/Concepts/Attention Mechanism.md",
            content=content,
        )
        _seed_raw_chunk(vault_path, relative_path="Raw/notes.md", text="attention from raw chunk")
        monkeypatch.setattr(
            "llm_wiki_backend.ask.service.get_ask_llm_provider",
            lambda vault: FakeAskProvider({"answer": "Use attention weights.", "unsupported": False, "citation_ids": ["W1"]}),
        )
        before = (vault_path / "Wiki/Concepts/Attention Mechanism.md").read_text(encoding="utf-8")
        response = client.post("/ask/query", params={"vault_path": str(vault_path)}, json={"question": "What is attention?"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["unsupported"] is False
        assert payload["trace"]["wiki_primary_count"] >= 1
        assert payload["trace"]["raw_used"] is False
        assert payload["citations"][0]["kind"] == "wiki"
        after = (vault_path / "Wiki/Concepts/Attention Mechanism.md").read_text(encoding="utf-8")
        assert before == after
        with _connect_db(vault_path) as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM proposed_updates").fetchone()["c"]
            assert count == 0
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase5_query_uses_raw_when_wiki_is_missing(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        _seed_raw_chunk(vault_path, relative_path="Raw/attention.md", text="Attention normalizes scores.", heading="Attention")
        monkeypatch.setattr(
            "llm_wiki_backend.ask.service.get_ask_llm_provider",
            lambda vault: FakeAskProvider({"answer": "Raw evidence says attention normalizes scores.", "unsupported": False, "citation_ids": ["R1"]}),
        )
        response = client.post("/ask/query", params={"vault_path": str(vault_path)}, json={"question": "attention normalization"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["trace"]["wiki_primary_count"] == 0
        assert payload["trace"]["raw_used"] is True
        assert payload["citations"][0]["kind"] == "raw"
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase5_rejects_hallucinated_citation(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        _seed_wiki_page(
            vault_path,
            title="Transformer",
            relative_path="Wiki/Entities/Transformer.md",
            content="# Transformer\n\nArchitecture.\n",
        )
        monkeypatch.setattr(
            "llm_wiki_backend.ask.service.get_ask_llm_provider",
            lambda vault: FakeAskProvider({"answer": "bad citation", "unsupported": False, "citation_ids": ["W9"]}),
        )
        response = client.post("/ask/query", params={"vault_path": str(vault_path)}, json={"question": "transformer"})
        assert response.status_code == 400
        assert "Unsupported citation id" in response.json()["detail"]
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase5_propose_update_creates_reviewable_proposal(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        target_rel = "Wiki/Concepts/Attention Mechanism.md"
        _seed_wiki_page(
            vault_path,
            title="Attention Mechanism",
            relative_path=target_rel,
            content="# Attention Mechanism\n\nBaseline content.\n",
        )
        before = (vault_path / target_rel).read_text(encoding="utf-8")
        response = client.post(
            "/ask/propose-update",
            params={"vault_path": str(vault_path)},
            json={
                "question": "What changed?",
                "answer": "Scaled attention helps numerical stability.",
                "target_relative_path": target_rel,
                "target_title": "Attention Mechanism",
                "reason": "Proposed from Ask",
                "source_citations": [{"locator": "Wiki/Concepts/Attention Mechanism.md"}],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["proposal_id"]
        assert payload["review_path"].startswith("Wiki/Reviews/")
        after = (vault_path / target_rel).read_text(encoding="utf-8")
        assert before == after
        with _connect_db(vault_path) as conn:
            proposal = conn.execute(
                "SELECT status, target_relative_path, source_relative_path FROM proposed_updates WHERE id = ?",
                (payload["proposal_id"],),
            ).fetchone()
            assert proposal is not None
            assert proposal["status"] == "pending"
            assert proposal["target_relative_path"] == target_rel
            assert proposal["source_relative_path"] == "Ask"
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)
