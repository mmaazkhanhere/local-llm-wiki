from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from llm_wiki_backend.main import app

client = TestClient(app)


class SequencedProvider:
    def __init__(self, payloads):
        self._payloads = list(payloads)

    def complete_structured(self, *, system_prompt: str, user_prompt: str, schema: dict):
        if not self._payloads:
            raise AssertionError("No payload left for fake provider")
        return self._payloads.pop(0)


def _connect_db(vault_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(vault_path / ".llm-wiki" / "app.db")
    conn.row_factory = sqlite3.Row
    return conn


def _bootstrap(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200


def _seed_proposal(vault_path: Path, monkeypatch) -> tuple[dict, Path]:
    vault_path.mkdir(parents=True, exist_ok=True)
    _bootstrap(vault_path)
    monkeypatch.setattr(
        "llm_wiki_backend.wiki.service.get_wiki_llm_provider",
        lambda vault: SequencedProvider(
            [
                {
                    "candidates": [
                        {
                            "page_type": "concept",
                            "title": "Attention Mechanism",
                            "summary": "How a model focuses on relevant tokens.",
                            "content_markdown": "Attention scores weight which tokens matter most during computation.",
                            "wiki_links": ["Transformer"],
                            "sources": [{"locator": 'section "Attention"'}],
                        }
                    ],
                    "flashcards": [],
                },
                {
                    "related_pages": [
                        {
                            "target_title": "Attention Mechanism",
                            "reason": "The new source adds a more specific explanation about scaled attention scores.",
                            "confidence": "high",
                            "source_citations": [{"locator": 'section "Scaled Attention"'}],
                            "proposed_content": "# Attention Mechanism\n\nHow a model focuses on relevant tokens.\n\nAttention scores weight which tokens matter most during computation.\n\nScaled attention normalizes score magnitude before softmax so long token sequences remain stable.\n\n## Related\n\n- [[Transformer]]\n\n## Sources\n\n- Source: `Raw/transformers.md`, section \"Attention\" \n- Source: `Raw/transformers-v2.md`, section \"Scaled Attention\"\n",
                        }
                    ]
                },
            ]
        ),
    )

    (vault_path / "Raw" / "transformers.md").write_text(
        "# Transformers\n\n## Attention\n\nAttention weights relevant tokens.\n",
        encoding="utf-8",
    )
    first_run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert first_run.status_code == 200
    target_page = vault_path / "Wiki" / "Concepts" / "Attention Mechanism.md"

    (vault_path / "Raw" / "transformers-v2.md").write_text(
        "# Transformers v2\n\n## Scaled Attention\n\nScaled attention normalizes score magnitude before softmax.\n",
        encoding="utf-8",
    )
    second_run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert second_run.status_code == 200
    return second_run.json(), target_page


def test_phase4_creates_proposed_update_without_touching_existing_page(
    monkeypatch,
) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        payload, target_page = _seed_proposal(vault_path, monkeypatch)
        original_page = target_page.read_text(encoding="utf-8")
        assert "Scaled attention" not in original_page

        assert payload["wiki_generation"]["proposed_update_count"] == 1
        source_result = payload["wiki_generation"]["source_results"][0]
        assert source_result["proposed_updates"][0]["target_path"] == "Wiki/Concepts/Attention Mechanism.md"
        assert "specific explanation" in source_result["proposed_updates"][0]["reason"]

        assert target_page.read_text(encoding="utf-8") == original_page

        review_files = list((vault_path / "Wiki" / "Reviews").glob("*.md"))
        assert len(review_files) == 1
        review_content = review_files[0].read_text(encoding="utf-8")
        assert "Attention Mechanism" in review_content
        assert "Scaled Attention" in review_content

        with _connect_db(vault_path) as conn:
            row = conn.execute(
                "SELECT status, reason, source_relative_path, target_relative_path FROM proposed_updates"
            ).fetchone()
            assert row is not None
            assert row["status"] == "pending"
            assert row["source_relative_path"] == "Raw/transformers-v2.md"
            assert row["target_relative_path"] == "Wiki/Concepts/Attention Mechanism.md"
            audit_event = conn.execute(
                "SELECT event_type FROM audit_events WHERE event_type = 'proposal_created'"
            ).fetchone()
            assert audit_event is not None
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase4_edit_approve_reject_and_conflict_routes(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        payload, target_page = _seed_proposal(vault_path, monkeypatch)
        proposal_id = payload["wiki_generation"]["source_results"][0]["proposed_updates"][0]["proposal_id"]

        list_response = client.get("/reviews", params={"vault_path": str(vault_path)})
        assert list_response.status_code == 200
        assert len(list_response.json()["proposals"]) == 1

        detail_response = client.get(f"/reviews/{proposal_id}", params={"vault_path": str(vault_path)})
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["diff"]

        edited_content = detail["proposed_content"].replace(
            "long token sequences remain stable.",
            "large attention values remain numerically stable.",
        )
        edit_response = client.put(
            f"/reviews/{proposal_id}",
            params={"vault_path": str(vault_path)},
            json={"proposed_content": edited_content},
        )
        assert edit_response.status_code == 200
        assert "numerically stable" in edit_response.json()["proposed_content"]

        approve_response = client.post(f"/reviews/{proposal_id}/approve", params={"vault_path": str(vault_path)})
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"
        assert "numerically stable" in target_page.read_text(encoding="utf-8")

        with _connect_db(vault_path) as conn:
            status_row = conn.execute(
                "SELECT status FROM proposed_updates WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            assert status_row["status"] == "approved"
            events = {
                row["event_type"]
                for row in conn.execute(
                    "SELECT event_type FROM audit_events WHERE event_type IN ('proposal_approved', 'target_file_written', 'log_updated')"
                ).fetchall()
            }
            assert {"proposal_approved", "target_file_written", "log_updated"} <= events

        payload2, _ = _seed_proposal(vault_path / "second", monkeypatch)
        proposal_id2 = payload2["wiki_generation"]["source_results"][0]["proposed_updates"][0]["proposal_id"]
        reject_response = client.post(
            f"/reviews/{proposal_id2}/reject",
            params={"vault_path": str(vault_path / 'second')},
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"

        pending_after_reject = client.get("/reviews", params={"vault_path": str(vault_path / 'second')})
        assert pending_after_reject.status_code == 200
        assert pending_after_reject.json()["proposals"] == []

        payload3, target_page3 = _seed_proposal(vault_path / "third", monkeypatch)
        proposal_id3 = payload3["wiki_generation"]["source_results"][0]["proposed_updates"][0]["proposal_id"]
        target_page3.write_text(target_page3.read_text(encoding="utf-8") + "\nManual change.\n", encoding="utf-8")
        conflict_response = client.post(
            f"/reviews/{proposal_id3}/approve",
            params={"vault_path": str(vault_path / 'third')},
        )
        assert conflict_response.status_code == 200
        assert conflict_response.json()["status"] == "conflicted"
        assert "Approve again to regenerate and apply" in conflict_response.json()["last_error"]
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase4_approve_all_updates_each_proposal_independently(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        monkeypatch.setattr(
            "llm_wiki_backend.wiki.service.get_wiki_llm_provider",
            lambda vault: SequencedProvider(
                [
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
                        ],
                        "flashcards": [],
                    },
                    {
                        "related_pages": [
                            {
                                "target_title": "Attention Mechanism",
                                "reason": "Adds a clearer scaling detail.",
                                "confidence": "high",
                                "source_citations": [{"locator": 'section "Scaled Attention"'}],
                                "proposed_content": "# Attention Mechanism\n\nHow a model focuses on relevant tokens.\n\nAttention scores weight which tokens matter most during computation.\n\nScaled attention normalizes score magnitude before softmax.\n\n## Related\n\n- [[Transformer]]\n\n## Sources\n\n- Source: `Raw/base.md`, section \"Attention\"\n- Source: `Raw/update.md`, section \"Scaled Attention\"\n",
                            },
                            {
                                "target_title": "Transformer",
                                "reason": "Adds the relationship to scaled attention.",
                                "confidence": "medium",
                                "source_citations": [{"locator": 'section "Scaled Attention"'}],
                                "proposed_content": "# Transformer\n\nA neural network architecture built around attention.\n\nTransformers stack attention and feed-forward blocks.\n\nScaled attention improves stability for larger score magnitudes.\n\n## Related\n\n- [[Attention Mechanism]]\n\n## Sources\n\n- Source: `Raw/base.md`, section \"Architecture\"\n- Source: `Raw/update.md`, section \"Scaled Attention\"\n",
                            },
                        ]
                    },
                ]
            ),
        )
        (vault_path / "Raw" / "base.md").write_text(
            "# Transformers\n\n## Attention\n\nAttention weights relevant tokens.\n\n## Architecture\n\nTransformers stack attention and feed-forward blocks.\n",
            encoding="utf-8",
        )
        assert client.post("/ingest/raw/run", params={"vault_path": str(vault_path)}).status_code == 200
        (vault_path / "Raw" / "update.md").write_text(
            "# Update\n\n## Scaled Attention\n\nScaled attention normalizes score magnitude before softmax.\n",
            encoding="utf-8",
        )
        second_run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
        assert second_run.status_code == 200

        transformer_page = vault_path / "Wiki" / "Entities" / "Transformer.md"
        transformer_page.write_text(transformer_page.read_text(encoding="utf-8") + "\nConcurrent edit.\n", encoding="utf-8")

        approve_all = client.post(
            "/reviews/approve-all",
            params={"vault_path": str(vault_path), "source_relative_path": "Raw/update.md"},
        )
        assert approve_all.status_code == 200
        assert approve_all.json() == {"applied": 1, "conflicted": 1, "failed": 0}

        attention_page = vault_path / "Wiki" / "Concepts" / "Attention Mechanism.md"
        assert "Scaled attention normalizes" in attention_page.read_text(encoding="utf-8")
        assert "Concurrent edit." in transformer_page.read_text(encoding="utf-8")
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)
