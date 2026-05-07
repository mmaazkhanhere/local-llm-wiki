from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llm_wiki_backend.wiki.markdown import atomic_write_text


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def record_audit_event(
    conn,
    *,
    vault_path: Path,
    event_type: str,
    summary: str,
    proposal_id: str | None = None,
    ingest_run_id: str | None = None,
    source_file: str | None = None,
    source_id: str | None = None,
    source_version: str | None = None,
    target_file: str | None = None,
    action: str | None = None,
    model: str | None = None,
    old_hash: str | None = None,
    new_hash: str | None = None,
    status: str | None = None,
    extra_details: dict[str, Any] | None = None,
) -> None:
    timestamp = now_iso()
    details = {
        "timestamp": timestamp,
        "event_type": event_type,
        "proposal_id": proposal_id,
        "ingest_run_id": ingest_run_id,
        "source_file": source_file,
        "source_id": source_id,
        "source_version": source_version,
        "target_file": target_file,
        "action": action,
        "model": model,
        "old_hash": old_hash,
        "new_hash": new_hash,
        "status": status,
    }
    if extra_details:
        details.update(extra_details)

    conn.execute(
        """
        INSERT INTO audit_events(id, event_type, target_path, source_paths_json, summary, details_json, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            event_type,
            target_file,
            json.dumps([source_file] if source_file else []),
            summary,
            json.dumps(details, ensure_ascii=False),
            timestamp,
        ),
    )
    _append_jsonl(vault_path / ".llm-wiki" / "audit.jsonl", details)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    content = existing + json.dumps(payload, ensure_ascii=False) + "\n"
    atomic_write_text(path, content)
