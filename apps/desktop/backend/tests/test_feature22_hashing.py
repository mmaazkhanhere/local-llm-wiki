from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

import pytest

from llm_wiki_backend.ingestion.service import (
    hash_discovered_files,
    list_raw_inbox,
    process_queued_files,
    scan_raw_files,
)
from llm_wiki_backend.vault.service import create_required_directories


@pytest.fixture
def vault_path() -> Path:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"vault-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    create_required_directories(path)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_feature22_hashes_every_discovered_file(vault_path: Path) -> None:
    raw = vault_path / "Raw"
    file_a = raw / "a.md"
    file_b = raw / "b.txt"
    file_a.write_text("# A\n", encoding="utf-8")
    file_b.write_text("hello", encoding="utf-8")

    scan = scan_raw_files(vault_path)
    assert scan.discovered_count == 2

    hashed = hash_discovered_files(vault_path)
    assert hashed.queued_count == 2
    assert hashed.skipped_count == 0

    rows = {item.relative_path: item for item in list_raw_inbox(vault_path)}
    assert rows["Raw/a.md"].sha256 == hashlib.sha256(file_a.read_bytes()).hexdigest()
    assert rows["Raw/b.txt"].sha256 == hashlib.sha256(file_b.read_bytes()).hexdigest()
    assert rows["Raw/a.md"].processing_status == "queued"
    assert rows["Raw/b.txt"].processing_status == "queued"


def test_feature22_unchanged_processed_files_are_skipped(vault_path: Path) -> None:
    source = vault_path / "Raw" / "unchanged.txt"
    source.write_text("same content", encoding="utf-8")

    scan_raw_files(vault_path)
    first_hash = hash_discovered_files(vault_path)
    assert first_hash.queued_count == 1

    processed = process_queued_files(vault_path)
    assert processed.processed_count == 1

    second_hash = hash_discovered_files(vault_path)
    assert second_hash.queued_count == 0
    assert second_hash.skipped_count == 1

    rows = {item.relative_path: item for item in list_raw_inbox(vault_path)}
    assert rows["Raw/unchanged.txt"].processing_status == "skipped_unchanged"


def test_feature22_detects_changed_content_even_when_timestamp_is_restored(vault_path: Path) -> None:
    source = vault_path / "Raw" / "same-name.txt"
    source.write_text("alpha", encoding="utf-8")

    scan_raw_files(vault_path)
    hash_discovered_files(vault_path)
    process_queued_files(vault_path)

    before = {item.relative_path: item for item in list_raw_inbox(vault_path)}["Raw/same-name.txt"]
    original_mtime = source.stat().st_mtime

    source.write_text("bravo", encoding="utf-8")
    os.utime(source, (original_mtime, original_mtime))

    hashed = hash_discovered_files(vault_path)
    assert hashed.queued_count == 1

    after = {item.relative_path: item for item in list_raw_inbox(vault_path)}["Raw/same-name.txt"]
    assert after.sha256 != before.sha256
    assert after.processing_status == "queued"


def test_feature22_hashing_does_not_modify_raw_file_content(vault_path: Path) -> None:
    source = vault_path / "Raw" / "immutable.txt"
    source.write_text("do not mutate me", encoding="utf-8")
    before_bytes = source.read_bytes()

    scan_raw_files(vault_path)
    hash_discovered_files(vault_path)

    assert source.read_bytes() == before_bytes
