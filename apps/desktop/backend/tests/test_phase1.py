from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm_wiki_backend.core.config import load_config, save_config
from llm_wiki_backend.core.errors import ConfigError
from llm_wiki_backend.core.models import AppConfig
from llm_wiki_backend.main import app
from llm_wiki_backend.vault.service import detect_obsidian_cli

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


def test_bootstrap_does_not_modify_unrelated_files(tmp_path: Path) -> None:
    notes = tmp_path / "Personal"
    notes.mkdir()
    untouched = notes / "note.md"
    untouched.write_text("do not change", encoding="utf-8")
    before = untouched.read_text(encoding="utf-8")

    response = client.post("/vault/bootstrap", json={"path": str(tmp_path)})
    assert response.status_code == 200

    after = untouched.read_text(encoding="utf-8")
    assert after == before


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


def test_config_roundtrip_read_write(tmp_path: Path) -> None:
    config = AppConfig(vault_path=str(tmp_path))
    save_config(config, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded is not None
    assert loaded.vault_path == str(tmp_path)


def test_config_invalid_json_raises_error(tmp_path: Path) -> None:
    config_dir = tmp_path / ".llm-wiki"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_config_invalid_schema_raises_error(tmp_path: Path) -> None:
    config_dir = tmp_path / ".llm-wiki"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text('{"provider": {"provider": "groq"}}', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_detect_obsidian_cli_when_not_installed(monkeypatch) -> None:
    monkeypatch.setattr("llm_wiki_backend.vault.service.shutil.which", lambda _: None)
    assert detect_obsidian_cli() is False
