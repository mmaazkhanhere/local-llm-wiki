from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

from llm_wiki_backend.ingestion.extractors import supported_file_type
from llm_wiki_backend.ingestion.service import PROTECTED_FOLDERS, process_single_path


@dataclass(frozen=True)
class WatcherStatus:
    running: bool
    vault_path: str | None
    poll_interval_seconds: float
    stabilize_seconds: float


class RawWatcherManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._vault_path: Path | None = None
        self._poll_interval_seconds: float = 1.0
        self._stabilize_seconds: float = 0.8
        self._fingerprints: dict[Path, tuple[int, int]] = {}
        self._pending: dict[Path, tuple[float, tuple[int, int]]] = {}

    def start(self, vault_path: Path, poll_interval_seconds: float = 1.0, stabilize_seconds: float = 0.8) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self._vault_path == vault_path:
                    return
                self._request_stop_locked()

            self._stop_event = threading.Event()
            self._vault_path = vault_path
            self._poll_interval_seconds = poll_interval_seconds
            self._stabilize_seconds = stabilize_seconds
            self._fingerprints = {}
            self._pending = {}
            self._thread = threading.Thread(target=self._run_loop, name="raw-watcher", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._request_stop_locked()

    def status(self) -> WatcherStatus:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            return WatcherStatus(
                running=running,
                vault_path=str(self._vault_path) if self._vault_path else None,
                poll_interval_seconds=self._poll_interval_seconds,
                stabilize_seconds=self._stabilize_seconds,
            )

    def _request_stop_locked(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._stop_event = None
        self._vault_path = None
        self._fingerprints = {}
        self._pending = {}

    def _run_loop(self) -> None:
        assert self._vault_path is not None
        assert self._stop_event is not None
        raw_root = self._vault_path / "Raw"

        while not self._stop_event.is_set():
            if raw_root.exists() and raw_root.is_dir():
                current = self._collect_fingerprints(raw_root)
                now = time.monotonic()

                for file_path, fingerprint in current.items():
                    old = self._fingerprints.get(file_path)
                    if old != fingerprint:
                        self._pending[file_path] = (now, fingerprint)

                removed = set(self._pending.keys()) - set(current.keys())
                for path in removed:
                    self._pending.pop(path, None)

                for file_path, (changed_at, expected_fingerprint) in list(self._pending.items()):
                    latest = current.get(file_path)
                    if latest is None:
                        self._pending.pop(file_path, None)
                        continue
                    if latest != expected_fingerprint:
                        self._pending[file_path] = (now, latest)
                        continue
                    if now - changed_at < self._stabilize_seconds:
                        continue
                    process_single_path(self._vault_path, file_path)
                    self._pending.pop(file_path, None)

                self._fingerprints = current

            self._stop_event.wait(self._poll_interval_seconds)

    def _collect_fingerprints(self, raw_root: Path) -> dict[Path, tuple[int, int]]:
        fingerprints: dict[Path, tuple[int, int]] = {}
        for candidate in raw_root.rglob("*"):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(raw_root)
            if _is_excluded_raw_relative(relative):
                continue
            file_type = supported_file_type(candidate)
            if file_type == "unsupported":
                continue
            stat = candidate.stat()
            fingerprints[candidate.resolve()] = (int(stat.st_size), int(stat.st_mtime_ns))
        return fingerprints


def _is_excluded_raw_relative(relative_path: Path) -> bool:
    parts = [part.lower() for part in relative_path.parts]
    return any(part in PROTECTED_FOLDERS for part in parts)


RAW_WATCHER = RawWatcherManager()
