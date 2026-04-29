from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki.core.vault import resolve_layout
from llm_wiki.wiki.index_page import rebuild_index_page


def repair_log_path(vault_root: Path) -> Path:
    layout = resolve_layout(vault_root)
    return layout.metadata_dir / "repair-state.jsonl"


def append_repair_event(
    vault_root: Path,
    *,
    event_type: str,
    source_relative_path: str,
    generated_relative_path: str,
    detail: str,
) -> None:
    path = repair_log_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "event_type": event_type,
        "source_relative_path": source_relative_path,
        "generated_relative_path": generated_relative_path,
        "detail": detail,
        "status": "open",
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def list_open_repairs(vault_root: Path) -> list[dict[str, str]]:
    path = repair_log_path(vault_root)
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("status") == "open":
            rows.append(payload)
    return rows


def run_repair(vault_root: Path) -> int:
    layout = resolve_layout(vault_root)
    rebuild_index_page(layout.index_file, layout.sources_dir, vault_root)
    # For MVP repair, rebuilding index is the deterministic safe fix.
    # Processing and audit logs are append-only and left unchanged.
    return len(list_open_repairs(vault_root))
