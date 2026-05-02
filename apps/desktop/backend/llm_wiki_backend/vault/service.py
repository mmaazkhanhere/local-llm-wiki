from __future__ import annotations

import shutil
from pathlib import Path

from llm_wiki_backend.core.errors import VaultValidationError

REQUIRED_DIRECTORIES = [
    Path("Raw"),
    Path("Wiki"),
    Path(".llm-wiki"),
    Path("Wiki/Concepts"),
    Path("Wiki/Entities"),
    Path("Wiki/Comparisons"),
    Path("Wiki/Maps"),
    Path("Wiki/Flashcards"),
    Path("Wiki/Reviews"),
]


def validate_vault(path_str: str) -> tuple[Path, bool]:
    vault_path = Path(path_str).expanduser().resolve()
    if not vault_path.exists():
        raise VaultValidationError("Vault path does not exist.")
    if not vault_path.is_dir():
        raise VaultValidationError("Vault path is not a directory.")
    has_obsidian = (vault_path / ".obsidian").is_dir()
    return vault_path, has_obsidian


def create_required_directories(vault_path: Path) -> list[str]:
    created: list[str] = []
    for rel in REQUIRED_DIRECTORIES:
        target = vault_path / rel
        if not target.exists():
            target.mkdir(parents=True, exist_ok=False)
            created.append(rel.as_posix())
    return created


def create_wiki_index_files(vault_path: Path) -> list[str]:
    created: list[str] = []
    files = {
        Path("Wiki/index.md"): "# Wiki Index\n\n## Concepts\n\n## Entities\n\n## Comparisons\n\n## Maps\n",
        Path("Wiki/log.md"): "# Processing Log\n",
    }
    for rel, content in files.items():
        target = vault_path / rel
        if not target.exists():
            target.write_text(content, encoding="utf-8")
            created.append(rel.as_posix())
    return created


def detect_git(vault_path: Path) -> bool:
    return (vault_path / ".git").is_dir()


def detect_obsidian_cli() -> bool:
    return shutil.which("obsidian") is not None
