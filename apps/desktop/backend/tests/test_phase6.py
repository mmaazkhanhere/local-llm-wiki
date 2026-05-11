from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from llm_wiki_backend.main import app

client = TestClient(app)


def _bootstrap(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200


def _connect_db(vault_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(vault_path / ".llm-wiki" / "app.db")
    conn.row_factory = sqlite3.Row
    return conn


def test_phase6_lint_auto_runs_after_ingest(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        # Avoid LLM usage during the ingest path; lint should still run.
        monkeypatch.setattr("llm_wiki_backend.wiki.service.get_wiki_llm_provider", lambda _vault: None)

        raw_file = vault_path / "Raw" / "note.md"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text("# Note\n\nHello.\n", encoding="utf-8")

        response = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)}, json={})
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("ingest_run_id")
        assert payload.get("lint") is not None
        assert payload["lint"]["status"] in {"clean", "lint_failed", "warnings", "needs_review", "mechanical_errors"}

        with _connect_db(vault_path) as conn:
            row = conn.execute("SELECT ingest_run_id, status FROM lint_runs ORDER BY started_at DESC LIMIT 1").fetchone()
            assert row is not None
            assert row["ingest_run_id"] == payload["ingest_run_id"]
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_latest_lint_endpoint_returns_summary(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        monkeypatch.setattr("llm_wiki_backend.wiki.service.get_wiki_llm_provider", lambda _vault: None)

        raw_file = vault_path / "Raw" / "note.md"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text("hello", encoding="utf-8")

        response = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)}, json={})
        assert response.status_code == 200

        status = client.get("/lint/latest", params={"vault_path": str(vault_path)})
        assert status.status_code == 200
        payload = status.json()
        assert payload["latest"] is not None
        assert payload["latest"]["lint_run_id"]
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_mechanical_lint_finds_broken_link_and_missing_index_entry(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        monkeypatch.setattr("llm_wiki_backend.wiki.service.get_wiki_llm_provider", lambda _vault: None)

        # Seed a wiki page with a broken wikilink and missing index entry.
        page_rel = "Wiki/Concepts/Alpha.md"
        page_path = vault_path / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text("# Alpha\n\nSee [[Does Not Exist]].\n", encoding="utf-8")

        # Empty index means Alpha is missing from index.md.
        (vault_path / "Wiki" / "index.md").write_text("# Index\n", encoding="utf-8")

        response = client.post("/lint/run", params={"vault_path": str(vault_path)})
        assert response.status_code == 200

        with _connect_db(vault_path) as conn:
            rows = conn.execute(
                "SELECT issue_type, severity FROM lint_issues ORDER BY created_at ASC"
            ).fetchall()
            types = {(row["issue_type"], row["severity"]) for row in rows}
            assert ("broken_internal_link", "error") in types
            assert ("missing_index_entry", "warning") in types
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_mechanical_lint_flags_broken_source_and_frontmatter(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        monkeypatch.setattr("llm_wiki_backend.wiki.service.get_wiki_llm_provider", lambda _vault: None)

        page_rel = "Wiki/Concepts/Beta.md"
        page_path = vault_path / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(
            "---\nkey: value\n\n# Beta\n\n## Sources\n\n- Source: `Raw/missing.md`, section \"X\"\n",
            encoding="utf-8",
        )

        response = client.post("/lint/run", params={"vault_path": str(vault_path)})
        assert response.status_code == 200

        with _connect_db(vault_path) as conn:
            rows = conn.execute(
                "SELECT issue_type FROM lint_issues WHERE page_relative_path = ?",
                (page_rel,),
            ).fetchall()
            types = {row["issue_type"] for row in rows}
            assert "broken_source_reference" in types
            assert "invalid_frontmatter" in types
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_provenance_lint_flags_missing_sources(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        monkeypatch.setattr("llm_wiki_backend.wiki.service.get_wiki_llm_provider", lambda _vault: None)

        page_rel = "Wiki/Concepts/Gamma.md"
        page_path = vault_path / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text("# Gamma\n\nNo sources here.\n", encoding="utf-8")

        response = client.post("/lint/run", params={"vault_path": str(vault_path)})
        assert response.status_code == 200

        with _connect_db(vault_path) as conn:
            rows = conn.execute(
                "SELECT issue_type, severity FROM lint_issues WHERE page_relative_path = ?",
                (page_rel,),
            ).fetchall()
            assert ("missing_source_reference", "warning") in {(r["issue_type"], r["severity"]) for r in rows}
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_safe_fix_adds_missing_index_entry_dry_run_and_apply(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)
    try:
        _bootstrap(vault_path)
        monkeypatch.setattr("llm_wiki_backend.wiki.service.get_wiki_llm_provider", lambda _vault: None)

        page_rel = "Wiki/Concepts/Delta.md"
        page_path = vault_path / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text("# Delta\n\nSummary line.\n\n## Sources\n\n- Source: `Raw/x.md`, section \"Y\"\n", encoding="utf-8")
        (vault_path / "Raw" / "x.md").write_text("raw", encoding="utf-8")
        (vault_path / "Wiki" / "index.md").write_text("# Index\n\n## Concepts\n\n", encoding="utf-8")

        lint = client.post("/lint/run", params={"vault_path": str(vault_path)}).json()["result"]
        lint_run_id = lint["lint_run_id"]

        before = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8")
        dry = client.post(
            "/lint/fix/apply",
            params={"vault_path": str(vault_path), "lint_run_id": lint_run_id, "dry_run": "true"},
        )
        assert dry.status_code == 200
        assert dry.json()["planned"] >= 1
        assert (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8") == before

        applied = client.post(
            "/lint/fix/apply",
            params={"vault_path": str(vault_path), "lint_run_id": lint_run_id, "dry_run": "false"},
        )
        assert applied.status_code == 200
        after = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8")
        assert after != before
        assert "[[Delta]]" in after
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_semantic_lint_records_issues(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)

    class FakeSemanticProvider:
        def complete_structured(self, *, system_prompt: str, user_prompt: str, schema: dict):
            return {
                "issues": [
                    {
                        "issue_type": "contradiction",
                        "severity": "warning",
                        "affected_pages": ["Wiki/Concepts/Zeta.md"],
                        "summary": "Two pages disagree about X.",
                        "evidence": ["Excerpt A", "Excerpt B"],
                    }
                ]
            }

    try:
        _bootstrap(vault_path)
        # Seed a wiki page row so semantic lint has something to scan.
        page_rel = "Wiki/Concepts/Zeta.md"
        page_path = vault_path / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text("# Zeta\n\nClaim.\n\n## Sources\n\n- Source: `Raw/a.md`, section \"B\"\n", encoding="utf-8")
        (vault_path / "Raw" / "a.md").write_text("raw", encoding="utf-8")

        with _connect_db(vault_path) as conn:
            now = "2026-05-11T00:00:00Z"
            page_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO wiki_pages(id, extraction_id, page_type, path, relative_path, sha256, title, summary, created_at, updated_at, status)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (page_id, None, "concept", str(page_path), page_rel, "seed", "Zeta", "seed", now, now, "generated"),
            )
            conn.commit()

        monkeypatch.setattr("llm_wiki_backend.lint.service.get_wiki_llm_provider", lambda _vault: FakeSemanticProvider())
        lint = client.post("/lint/run", params={"vault_path": str(vault_path), "semantic": "true"}).json()["result"]
        assert lint["semantic_recorded_count"] == 1

        with _connect_db(vault_path) as conn:
            row = conn.execute(
                "SELECT issue_type, severity FROM lint_issues WHERE issue_type = 'contradiction' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            assert row is not None
            assert row["severity"] == "warning"
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)


def test_phase6_review_pages_created_from_semantic_issues_and_deduped(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    vault_path = root / f"vault-{uuid.uuid4().hex}"
    vault_path.mkdir(parents=True, exist_ok=False)

    class FakeSemanticProvider:
        def complete_structured(self, *, system_prompt: str, user_prompt: str, schema: dict):
            return {
                "issues": [
                    {
                        "issue_type": "contradiction",
                        "severity": "warning",
                        "affected_pages": ["Wiki/Concepts/Zeta.md"],
                        "summary": "Disagreement about X.",
                        "evidence": ["A", "B"],
                    }
                ]
            }

    try:
        _bootstrap(vault_path)
        page_rel = "Wiki/Concepts/Zeta.md"
        page_path = vault_path / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text("# Zeta\n\nClaim.\n\n## Sources\n\n- Source: `Raw/a.md`, section \"B\"\n", encoding="utf-8")
        (vault_path / "Raw" / "a.md").write_text("raw", encoding="utf-8")

        with _connect_db(vault_path) as conn:
            now = "2026-05-11T00:00:00Z"
            page_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO wiki_pages(id, extraction_id, page_type, path, relative_path, sha256, title, summary, created_at, updated_at, status)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (page_id, None, "concept", str(page_path), page_rel, "seed", "Zeta", "seed", now, now, "generated"),
            )
            conn.commit()

        monkeypatch.setattr("llm_wiki_backend.lint.service.get_wiki_llm_provider", lambda _vault: FakeSemanticProvider())
        lint = client.post("/lint/run", params={"vault_path": str(vault_path), "semantic": "true"}).json()["result"]
        lint_run_id = lint["lint_run_id"]

        created_1 = client.post(
            "/lint/reviews/create",
            params={"vault_path": str(vault_path), "lint_run_id": lint_run_id},
        )
        assert created_1.status_code == 200
        payload_1 = created_1.json()
        assert len(payload_1["created"]) == 1
        review_rel = payload_1["created"][0]["review_relative_path"]
        assert (vault_path / review_rel).exists()

        # Second create call should not duplicate.
        created_2 = client.post(
            "/lint/reviews/create",
            params={"vault_path": str(vault_path), "lint_run_id": lint_run_id},
        )
        assert created_2.status_code == 200
        assert created_2.json()["created"] == []
    finally:
        client.post("/ingest/raw/watch/stop")
        shutil.rmtree(vault_path, ignore_errors=True)
