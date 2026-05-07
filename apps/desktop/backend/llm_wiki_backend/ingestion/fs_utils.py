from __future__ import annotations

import hashlib
from pathlib import Path

PROTECTED_FOLDERS = {"wiki", ".llm-wiki", ".obsidian", ".git", ".trash"}


def iter_raw_files(vault_path: Path):
    raw_root = vault_path / "Raw"
    if not raw_root.exists() or not raw_root.is_dir():
        return
    for candidate in raw_root.rglob("*"):
        if not candidate.is_file():
            continue
        yield candidate


def is_protected_relative(relative_path: Path) -> bool:
    parts = [part.lower() for part in relative_path.parts]
    return any(part in PROTECTED_FOLDERS for part in parts)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()
