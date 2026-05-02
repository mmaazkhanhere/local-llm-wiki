from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from llm_wiki_backend.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body


def test_vault_select_warns_when_obsidian_missing(tmp_path: Path) -> None:
    response = client.post("/vault/select", json={"path": str(tmp_path)})
    assert response.status_code == 200
    body = response.json()
    assert body["has_obsidian"] is False
    assert body["warning"]


def test_vault_select_detects_obsidian(tmp_path: Path) -> None:
    (tmp_path / ".obsidian").mkdir()
    response = client.post("/vault/select", json={"path": str(tmp_path)})
    assert response.status_code == 200
    assert response.json()["has_obsidian"] is True


def test_bootstrap_creates_directories_files_db_and_config(tmp_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(tmp_path)})
    assert response.status_code == 200
    body = response.json()
    assert (tmp_path / "Raw").is_dir()
    assert (tmp_path / "Wiki").is_dir()
    assert (tmp_path / ".llm-wiki").is_dir()
    assert (tmp_path / "Wiki/index.md").is_file()
    assert (tmp_path / "Wiki/log.md").is_file()
    assert (tmp_path / ".llm-wiki/app.db").is_file()
    assert (tmp_path / ".llm-wiki/config.json").is_file()
    assert body["database_path"].endswith(".llm-wiki\\app.db") or body["database_path"].endswith(
        ".llm-wiki/app.db"
    )


def test_bootstrap_is_idempotent_for_existing_files(tmp_path: Path) -> None:
    first = client.post("/vault/bootstrap", json={"path": str(tmp_path)})
    assert first.status_code == 200
    index_path = tmp_path / "Wiki/index.md"
    original = index_path.read_text(encoding="utf-8")
    second = client.post("/vault/bootstrap", json={"path": str(tmp_path)})
    assert second.status_code == 200
    assert index_path.read_text(encoding="utf-8") == original


def test_database_contains_required_tables(tmp_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(tmp_path)})
    assert response.status_code == 200
    db_path = tmp_path / ".llm-wiki/app.db"
    expected = {
        "vaults",
        "files",
        "extractions",
        "chunks",
        "wiki_pages",
        "proposed_updates",
        "audit_events",
        "flashcards",
        "review_items",
    }
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    actual = {row[0] for row in rows}
    assert expected.issubset(actual)


def test_vault_configure_saves_config_and_detects_git(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    response = client.post("/vault/configure", json={"path": str(tmp_path)})
    assert response.status_code == 200
    body = response.json()
    assert body["git_detected"] is True
    assert (tmp_path / ".llm-wiki/config.json").is_file()


def test_provider_test_success_stores_secret(tmp_path: Path, monkeypatch) -> None:
    def fake_test(api_key: str, timeout_seconds: float = 10.0) -> tuple[bool, str]:
        assert api_key == "test-key"
        return True, "ok"

    monkeypatch.setattr("llm_wiki_backend.api.routes.test_groq_connection", fake_test)
    response = client.post(
        "/provider/groq/test",
        params={"vault_path": str(tmp_path)},
        json={"api_key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert (tmp_path / ".llm-wiki/secrets.enc.json").is_file()


def test_provider_test_failure_does_not_store_secret(tmp_path: Path, monkeypatch) -> None:
    def fake_test(api_key: str, timeout_seconds: float = 10.0) -> tuple[bool, str]:
        return False, "bad auth"

    monkeypatch.setattr("llm_wiki_backend.api.routes.test_groq_connection", fake_test)
    response = client.post(
        "/provider/groq/test",
        params={"vault_path": str(tmp_path)},
        json={"api_key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert not (tmp_path / ".llm-wiki/secrets.enc.json").exists()
