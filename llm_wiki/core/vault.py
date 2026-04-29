from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_wiki.core.config import APP_METADATA_DIRNAME


LLM_WIKI_DIRNAME = "LLM Wiki"


@dataclass(frozen=True)
class VaultLayout:
    vault_root: Path
    llm_wiki_dir: Path
    sources_dir: Path
    questions_dir: Path
    flashcards_dir: Path
    active_recall_dir: Path
    audit_dir: Path
    index_file: Path
    inbox_file: Path
    processing_log_file: Path
    metadata_dir: Path
    db_path: Path
    config_path: Path
    file_index_path: Path
    logs_dir: Path


def resolve_layout(vault_root: Path) -> VaultLayout:
    llm_wiki_dir = vault_root / LLM_WIKI_DIRNAME
    metadata_dir = vault_root / APP_METADATA_DIRNAME
    return VaultLayout(
        vault_root=vault_root,
        llm_wiki_dir=llm_wiki_dir,
        sources_dir=llm_wiki_dir / "Sources",
        questions_dir=llm_wiki_dir / "Questions",
        flashcards_dir=llm_wiki_dir / "Flashcards",
        active_recall_dir=llm_wiki_dir / "Active Recall",
        audit_dir=llm_wiki_dir / "Audit",
        index_file=llm_wiki_dir / "_Index.md",
        inbox_file=llm_wiki_dir / "_Inbox.md",
        processing_log_file=llm_wiki_dir / "_Processing Log.md",
        metadata_dir=metadata_dir,
        db_path=metadata_dir / "app.db",
        config_path=metadata_dir / "config.json",
        file_index_path=metadata_dir / "file_index.json",
        logs_dir=metadata_dir / "logs",
    )


def initialize_vault(vault_root: Path) -> VaultLayout:
    vault_root = vault_root.resolve()
    if not vault_root.exists() or not vault_root.is_dir():
        raise ValueError(f"Vault path does not exist or is not a directory: {vault_root}")

    layout = resolve_layout(vault_root)

    for directory in (
        layout.llm_wiki_dir,
        layout.sources_dir,
        layout.questions_dir,
        layout.flashcards_dir,
        layout.active_recall_dir,
        layout.audit_dir,
        layout.metadata_dir,
        layout.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _ensure_markdown_file(layout.index_file, "# LLM Wiki Index\n")
    _ensure_markdown_file(layout.inbox_file, "# LLM Wiki Inbox\n")
    _ensure_markdown_file(layout.processing_log_file, "# Processing Log\n")
    _ensure_text_file(layout.file_index_path, "{}\n")
    _ensure_text_file(layout.config_path, "{}\n")
    return layout


def is_path_in_raw_source_scope(path: Path, vault_root: Path) -> bool:
    return not is_excluded_from_ingestion(path, vault_root)


def is_excluded_from_ingestion(path: Path, vault_root: Path) -> bool:
    rel = path.resolve().relative_to(vault_root.resolve())
    top = rel.parts[0] if rel.parts else ""
    excluded = {"LLM Wiki", ".llm-wiki", ".obsidian", ".git", ".trash"}
    return top in excluded


def assert_app_owned_write_path(target_path: Path, vault_root: Path) -> None:
    vault_root = vault_root.resolve()
    target_path = target_path.resolve()
    try:
        rel = target_path.relative_to(vault_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes vault root: {target_path}") from exc
    top = rel.parts[0] if rel.parts else ""
    if top not in {"LLM Wiki", ".llm-wiki"}:
        raise ValueError(f"Writes are restricted to app-owned folders: {target_path}")


def normalize_and_validate_app_write_path(target_path: Path, vault_root: Path) -> Path:
    normalized = target_path.resolve()
    assert_app_owned_write_path(normalized, vault_root)
    return normalized


def _ensure_markdown_file(path: Path, initial_content: str) -> None:
    if not path.exists():
        path.write_text(initial_content, encoding="utf-8")


def _ensure_text_file(path: Path, initial_content: str) -> None:
    if not path.exists():
        path.write_text(initial_content, encoding="utf-8")
