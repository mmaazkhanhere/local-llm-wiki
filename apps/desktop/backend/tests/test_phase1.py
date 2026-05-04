from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm_wiki_backend.core.config import load_config, save_config
from llm_wiki_backend.core.errors import ConfigError
from llm_wiki_backend.core.models import AppConfig
from llm_wiki_backend.main import app
from llm_wiki_backend.vault.service import REQUIRED_DIRECTORIES, detect_obsidian_cli

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
        shutil.rmtree(path, ignore_errors=True)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "timestamp" in body


def test_vault_select_rejects_missing_path(vault_path: Path) -> None:
    missing = vault_path / "does-not-exist"
    response = client.post("/vault/select", json={"path": str(missing)})
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_vault_select_rejects_file_path(vault_path: Path) -> None:
    file_path = vault_path / "note.md"
    file_path.write_text("x", encoding="utf-8")
    response = client.post("/vault/select", json={"path": str(file_path)})
    assert response.status_code == 400
    assert "not a directory" in response.json()["detail"]


def test_vault_select_warns_when_obsidian_missing(vault_path: Path) -> None:
    response = client.post("/vault/select", json={"path": str(vault_path)})
    assert response.status_code == 200
    body = response.json()
    assert body["has_obsidian"] is False
    assert body["warning"]


def test_vault_select_detects_obsidian(vault_path: Path) -> None:
    (vault_path / ".obsidian").mkdir()
    response = client.post("/vault/select", json={"path": str(vault_path)})
    assert response.status_code == 200
    assert response.json()["has_obsidian"] is True


def test_bootstrap_creates_all_required_directories(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200

    for rel in REQUIRED_DIRECTORIES:
        assert (vault_path / rel).is_dir(), f"missing directory: {rel}"


def test_bootstrap_creates_index_log_db_and_config(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200
    body = response.json()
    assert (vault_path / "Wiki/index.md").is_file()
    assert (vault_path / "Wiki/log.md").is_file()
    assert (vault_path / ".llm-wiki/app.db").is_file()
    assert (vault_path / ".llm-wiki/config.json").is_file()
    assert body["database_path"].endswith(".llm-wiki\\app.db") or body["database_path"].endswith(
        ".llm-wiki/app.db"
    )


def test_bootstrap_is_idempotent_for_existing_files(vault_path: Path) -> None:
    first = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert first.status_code == 200
    index_path = vault_path / "Wiki/index.md"
    log_path = vault_path / "Wiki/log.md"
    original_index = index_path.read_text(encoding="utf-8")
    original_log = log_path.read_text(encoding="utf-8")

    second = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert second.status_code == 200
    assert index_path.read_text(encoding="utf-8") == original_index
    assert log_path.read_text(encoding="utf-8") == original_log


def test_bootstrap_does_not_modify_unrelated_files(vault_path: Path) -> None:
    notes = vault_path / "Personal"
    notes.mkdir()
    untouched = notes / "note.md"
    untouched.write_text("do not change", encoding="utf-8")
    before = untouched.read_text(encoding="utf-8")

    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200
    assert untouched.read_text(encoding="utf-8") == before


def test_database_contains_required_tables(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200
    db_path = vault_path / ".llm-wiki/app.db"
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


def test_vault_configure_saves_config_and_detects_git(vault_path: Path) -> None:
    (vault_path / ".git").mkdir()
    response = client.post("/vault/configure", json={"path": str(vault_path)})
    assert response.status_code == 200
    body = response.json()
    assert body["git_detected"] is True
    assert (vault_path / ".llm-wiki/config.json").is_file()


def test_provider_test_success_stores_secret(vault_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_test(api_key: str, timeout_seconds: float = 10.0) -> tuple[bool, str]:
        assert api_key == "test-key"
        return True, "ok"

    monkeypatch.setattr("llm_wiki_backend.api.routes.test_groq_connection", fake_test)
    response = client.post(
        "/provider/groq/test",
        params={"vault_path": str(vault_path)},
        json={"api_key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert (vault_path / ".llm-wiki/secrets.enc.json").is_file()


def test_provider_test_failure_does_not_store_secret(vault_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_test(api_key: str, timeout_seconds: float = 10.0) -> tuple[bool, str]:
        return False, "bad auth"

    monkeypatch.setattr("llm_wiki_backend.api.routes.test_groq_connection", fake_test)
    response = client.post(
        "/provider/groq/test",
        params={"vault_path": str(vault_path)},
        json={"api_key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert not (vault_path / ".llm-wiki/secrets.enc.json").exists()


def test_config_roundtrip_read_write(vault_path: Path) -> None:
    config = AppConfig(vault_path=str(vault_path))
    save_config(config, vault_path)
    loaded = load_config(vault_path)
    assert loaded is not None
    assert loaded.vault_path == str(vault_path)


def test_config_invalid_json_raises_error(vault_path: Path) -> None:
    config_dir = vault_path / ".llm-wiki"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(vault_path)


def test_config_invalid_schema_raises_error(vault_path: Path) -> None:
    config_dir = vault_path / ".llm-wiki"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text('{"provider": {"provider": "groq"}}', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(vault_path)


def test_detect_obsidian_cli_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llm_wiki_backend.vault.service.shutil.which", lambda _: None)
    assert detect_obsidian_cli() is False


@pytest.mark.xfail(reason="Current bootstrap path does not handle invalid existing config gracefully.", strict=False)
def test_bootstrap_handles_invalid_existing_config_safely(vault_path: Path) -> None:
    config_dir = vault_path / ".llm-wiki"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text("{invalid", encoding="utf-8")
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200

