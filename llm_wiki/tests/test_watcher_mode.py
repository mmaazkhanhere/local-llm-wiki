import queue
from pathlib import Path

from llm_wiki.core.watcher import (
    WatchSettings,
    drain_debounced_paths,
    to_scanned_file,
    wait_for_stable_file,
)


def test_drain_debounced_paths_deduplicates() -> None:
    q: "queue.Queue[Path]" = queue.Queue()
    p = Path("a.md")
    q.put(p)
    q.put(p)
    items = drain_debounced_paths(q, debounce_seconds=0.0)
    assert len(items) == 1
    assert items[0] == p


def test_wait_for_stable_file_true(tmp_path: Path) -> None:
    file_path = tmp_path / "note.md"
    file_path.write_text("hello", encoding="utf-8")
    settings = WatchSettings(debounce_seconds=0.0, stable_timeout_seconds=1.0, stable_poll_seconds=0.05)
    assert wait_for_stable_file(file_path, settings) is True


def test_to_scanned_file_maps_relative_path(tmp_path: Path) -> None:
    nested = tmp_path / "x" / "a.md"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("x", encoding="utf-8")
    scanned = to_scanned_file(nested, tmp_path)
    assert scanned.relative_path.as_posix() == "x/a.md"
    assert scanned.extension == ".md"
