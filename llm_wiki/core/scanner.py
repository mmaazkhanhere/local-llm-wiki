from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_wiki.core.vault import is_excluded_from_ingestion


SUPPORTED_EXTENSIONS = {
    ".md",
    ".txt",
    ".pdf",
    ".docx",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    relative_path: Path
    extension: str
    size_bytes: int


def scan_vault_sources(vault_root: Path) -> list[ScannedFile]:
    vault_root = vault_root.resolve()
    results: list[ScannedFile] = []
    for candidate in vault_root.rglob("*"):
        if not candidate.is_file():
            continue
        if _is_outside_vault(candidate, vault_root):
            continue
        if is_excluded_from_ingestion(candidate, vault_root):
            continue
        ext = candidate.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        rel = candidate.relative_to(vault_root)
        results.append(
            ScannedFile(
                path=candidate,
                relative_path=rel,
                extension=ext,
                size_bytes=candidate.stat().st_size,
            )
        )
    results.sort(key=lambda item: item.relative_path.as_posix().lower())
    return results


def _is_outside_vault(path: Path, vault_root: Path) -> bool:
    try:
        path.resolve().relative_to(vault_root.resolve())
        return False
    except ValueError:
        return True
