from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from llm_wiki.core.errors import ExtractionTransientError, WritePathError
from llm_wiki.core.retries import FILE_IO_RETRY_POLICY, with_retry
from llm_wiki.core.vault import normalize_and_validate_app_write_path, resolve_layout


def normalize_summary_filename(title: str, max_len: int = 120) -> str:
    cleaned = title.strip() or "Untitled"
    cleaned = re.sub(r'[<>:"/\\|?*]+', " - ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(". ")
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    return f"{cleaned} summary.md"


def resolve_summary_target_path(vault_root: Path, source_title: str) -> Path:
    layout = resolve_layout(vault_root)
    target = layout.sources_dir / normalize_summary_filename(source_title)
    if not target.exists():
        return target
    short_hash = hashlib.sha256(source_title.encode("utf-8")).hexdigest()[:8]
    stem = target.stem
    return target.with_name(f"{stem} ({short_hash}).md")


def atomic_write_markdown(target_path: Path, content: str, vault_root: Path) -> None:
    safe_target = normalize_and_validate_app_write_path(target_path, vault_root)
    safe_target.parent.mkdir(parents=True, exist_ok=True)

    def _write_once() -> None:
        try:
            with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=safe_target.parent) as temp:
                temp.write(content)
                temp.flush()
                temp_path = Path(temp.name)
            temp_path.replace(safe_target)
        except PermissionError as exc:
            raise ExtractionTransientError(f"Temporary file lock while writing {safe_target}") from exc
        except OSError as exc:
            raise WritePathError(f"Write failed for {safe_target}: {exc}") from exc

    with_retry(_write_once, FILE_IO_RETRY_POLICY)


def append_processing_log(
    processing_log_path: Path,
    *,
    source_relative_path: str,
    generated_relative_path: str,
) -> None:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    entry = (
        f"\n## {timestamp}\n\n"
        f"Processed source: `{source_relative_path}`\n\n"
        "Generated:\n\n"
        f"- [[{Path(generated_relative_path).stem}]]\n\n"
        "Status: Auto-generated\n"
    )
    with processing_log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def append_audit_jsonl(
    audit_log_jsonl_path: Path,
    *,
    event_type: str,
    source_path: str,
    generated_path: str,
    model_provider: str,
    model_name: str,
    content_hash: str,
) -> None:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    payload = {
        "timestamp": timestamp,
        "event_type": event_type,
        "source_path": source_path,
        "generated_paths": [generated_path],
        "model_provider": model_provider,
        "model": model_name,
        "content_hash": content_hash,
    }
    with audit_log_jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
