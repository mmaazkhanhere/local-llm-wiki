from pathlib import Path

from llm_wiki.core.scanner import scan_vault_sources
from llm_wiki.core.vault import initialize_vault


def test_scan_vault_filters_extensions_and_exclusions(tmp_path: Path) -> None:
    initialize_vault(tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text("# hello", encoding="utf-8")
    (tmp_path / "notes" / "b.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "notes" / "c.bin").write_bytes(b"\x00\x01")
    (tmp_path / "LLM Wiki" / "Sources" / "generated.md").write_text("ignore me", encoding="utf-8")
    (tmp_path / ".obsidian").mkdir(exist_ok=True)
    (tmp_path / ".obsidian" / "meta.md").write_text("ignore", encoding="utf-8")
    (tmp_path / ".git").mkdir(exist_ok=True)
    (tmp_path / ".git" / "hooks.md").write_text("ignore", encoding="utf-8")

    scanned = scan_vault_sources(tmp_path)
    rel_paths = [item.relative_path.as_posix() for item in scanned]

    assert "notes/a.md" in rel_paths
    assert "notes/b.txt" in rel_paths
    assert "notes/c.bin" not in rel_paths
    assert "LLM Wiki/Sources/generated.md" not in rel_paths
    assert ".obsidian/meta.md" not in rel_paths
    assert ".git/hooks.md" not in rel_paths


def test_scan_is_sorted_by_relative_path(tmp_path: Path) -> None:
    initialize_vault(tmp_path)
    (tmp_path / "z.md").write_text("z", encoding="utf-8")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    scanned = scan_vault_sources(tmp_path)
    rel_paths = [item.relative_path.as_posix() for item in scanned]
    assert rel_paths == sorted(rel_paths, key=str.lower)
