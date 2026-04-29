from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from llm_wiki.core.scanner import SUPPORTED_EXTENSIONS, ScannedFile
from llm_wiki.core.vault import is_excluded_from_ingestion


@dataclass(frozen=True)
class WatchSettings:
    debounce_seconds: float = 1.0
    stable_timeout_seconds: float = 10.0
    stable_poll_seconds: float = 0.25


class VaultWatchHandler(FileSystemEventHandler):
    def __init__(self, vault_root: Path, work_queue: "queue.Queue[Path]") -> None:
        super().__init__()
        self.vault_root = vault_root
        self.work_queue = work_queue

    def on_created(self, event):  # type: ignore[override]
        self._enqueue_event_path(event)

    def on_modified(self, event):  # type: ignore[override]
        self._enqueue_event_path(event)

    def _enqueue_event_path(self, event) -> None:
        if event.is_directory:
            return
        candidate = Path(event.src_path).resolve()
        if not candidate.exists() or not candidate.is_file():
            return
        if is_excluded_from_ingestion(candidate, self.vault_root):
            return
        if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        self.work_queue.put(candidate)


def start_observer(vault_root: Path, work_queue: "queue.Queue[Path]") -> Observer:
    handler = VaultWatchHandler(vault_root=vault_root, work_queue=work_queue)
    observer = Observer()
    observer.schedule(handler, str(vault_root), recursive=True)
    observer.start()
    return observer


def drain_debounced_paths(work_queue: "queue.Queue[Path]", debounce_seconds: float) -> list[Path]:
    time.sleep(max(0.0, debounce_seconds))
    seen: dict[str, Path] = {}
    while True:
        try:
            path = work_queue.get_nowait()
        except queue.Empty:
            break
        seen[str(path)] = path
    return list(seen.values())


def wait_for_stable_file(path: Path, settings: WatchSettings) -> bool:
    start = time.monotonic()
    last_size = -1
    last_mtime = -1.0
    stable_hits = 0
    while time.monotonic() - start < settings.stable_timeout_seconds:
        if not path.exists() or not path.is_file():
            return False
        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime
        if size == last_size and mtime == last_mtime:
            stable_hits += 1
            if stable_hits >= 2:
                return True
        else:
            stable_hits = 0
            last_size = size
            last_mtime = mtime
        time.sleep(settings.stable_poll_seconds)
    return False


def to_scanned_file(path: Path, vault_root: Path) -> ScannedFile:
    rel = path.resolve().relative_to(vault_root.resolve())
    return ScannedFile(
        path=path.resolve(),
        relative_path=rel,
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
    )
