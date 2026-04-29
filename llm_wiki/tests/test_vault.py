from pathlib import Path

import pytest

from llm_wiki.core.vault import assert_app_owned_write_path, initialize_vault, is_excluded_from_ingestion


def test_initialize_vault_creates_required_structure(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    assert layout.llm_wiki_dir.exists()
    assert layout.sources_dir.exists()
    assert layout.questions_dir.exists()
    assert layout.flashcards_dir.exists()
    assert layout.active_recall_dir.exists()
    assert layout.audit_dir.exists()
    assert layout.metadata_dir.exists()
    assert layout.db_path.parent.exists()
    assert layout.config_path.exists()
    assert layout.file_index_path.exists()


def test_write_guard_rejects_non_app_owned_path(tmp_path: Path) -> None:
    initialize_vault(tmp_path)
    outside = tmp_path / "raw-note.md"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        assert_app_owned_write_path(outside, tmp_path)


def test_write_guard_accepts_app_owned_path(tmp_path: Path) -> None:
    layout = initialize_vault(tmp_path)
    target = layout.sources_dir / "My summary.md"
    target.touch()
    assert_app_owned_write_path(target, tmp_path)


def test_exclusion_logic(tmp_path: Path) -> None:
    initialize_vault(tmp_path)
    excluded = tmp_path / "LLM Wiki" / "Sources" / "a.md"
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text("x", encoding="utf-8")
    assert is_excluded_from_ingestion(excluded, tmp_path)
