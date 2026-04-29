from __future__ import annotations

import argparse
import hashlib
import queue
import sqlite3
import time
from pathlib import Path

from llm_wiki.core.config import AppConfig, load_config, save_config
from llm_wiki.core.database import (
    Database,
    FILE_STATUS_DISCOVERED,
    FILE_STATUS_FAILED_TRANSIENT,
    FILE_STATUS_FAILED_PERMANENT,
    FILE_STATUS_GENERATED,
    FILE_STATUS_PROCESSING,
    FILE_STATUS_QUEUED,
    FILE_STATUS_SKIPPED_UNCHANGED,
    initialize_schema,
    get_file_by_relative_path,
    insert_audit_event,
    replace_chunks,
    set_file_status,
    upsert_generated_page,
    upsert_source_document,
    upsert_scanned_file,
    upsert_vault,
)
from llm_wiki.core.repair import append_repair_event, list_open_repairs, run_repair
from llm_wiki.core.scanner import scan_vault_sources
from llm_wiki.core.scanner import ScannedFile
from llm_wiki.core.watcher import (
    WatchSettings,
    drain_debounced_paths,
    start_observer,
    to_scanned_file,
    wait_for_stable_file,
)
from llm_wiki.core.secrets import load_groq_api_key, save_groq_api_key
from llm_wiki.core.vault import initialize_vault, resolve_layout
from llm_wiki.ingestion.chunking import chunk_text
from llm_wiki.ingestion.markdown import extract_markdown
from llm_wiki.ingestion.text import extract_text
from llm_wiki.llm.base import LLMProvider
from llm_wiki.llm.prompts import source_summary_system_prompt, source_summary_user_prompt
from llm_wiki.llm.groq_provider import GroqProvider
from llm_wiki.retrieval.qa import answer_question, render_qa_markdown
from llm_wiki.ui.dashboard import build_dashboard_data, render_dashboard_text
from llm_wiki.wiki.templates import render_source_summary_page
from llm_wiki.wiki.index_page import rebuild_index_page
from llm_wiki.wiki.writer import (
    append_audit_jsonl,
    append_processing_log,
    atomic_write_markdown,
    resolve_summary_target_path,
)


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local LLM Wiki foundation app")
    parser.add_argument("--vault", type=str, required=True, help="Path to an Obsidian vault")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Run an initial scan and persist discovered file states",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously watch the vault and process new/changed supported files",
    )
    parser.add_argument(
        "--watch-seconds",
        type=float,
        default=0.0,
        help="Optional timeout for watch mode. 0 runs until interrupted.",
    )
    parser.add_argument(
        "--provider-check",
        action="store_true",
        help="Validate configured provider credentials before other work",
    )
    parser.add_argument(
        "--provider-ping",
        action="store_true",
        help="Run a lightweight real provider connectivity check",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Show dashboard and recent activity from local state",
    )
    parser.add_argument(
        "--ask",
        type=str,
        default=None,
        help="Ask a question over processed summaries and source chunks",
    )
    parser.add_argument(
        "--repair-status",
        action="store_true",
        help="Show open repair-needed events",
    )
    parser.add_argument(
        "--repair-run",
        action="store_true",
        help="Run deterministic repair actions",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch desktop shell (PySide6) if available",
    )
    return parser.parse_args()


def internal_cli_main() -> int:
    args = _parse_cli_args()
    vault_root = Path(args.vault).resolve()
    layout = initialize_vault(vault_root)

    config = load_config(layout.config_path)
    if not config.groq_api_key:
        config.groq_api_key = load_groq_api_key(layout.metadata_dir)
    elif config.groq_api_key:
        save_groq_api_key(layout.metadata_dir, config.groq_api_key)
    if not config.vault_path:
        config = AppConfig(
            vault_path=str(vault_root),
            provider=config.provider,
            model=config.model,
            groq_api_key=config.groq_api_key,
            groq_base_url=config.groq_base_url,
            auto_process=config.auto_process,
            git_integration_enabled=config.git_integration_enabled,
        )
        save_config(config, layout.config_path)

    provider = build_provider(config)
    if args.provider_check:
        provider.validate_configuration()
    if args.provider_ping:
        ok, latency_ms, detail = provider_ping(provider)
        if ok:
            print(f"Provider ping OK ({provider.provider_name()}): {latency_ms:.1f}ms")
            return 0
        print(f"Provider ping FAILED ({provider.provider_name()}): {latency_ms:.1f}ms {detail}")
        return 2
    if args.ui:
        return run_desktop_shell(vault_root, config)

    db = Database(layout.db_path)
    with db.connect() as connection:
        initialize_schema(connection)
        vault_id = upsert_vault(connection, vault_root)
        if args.repair_status:
            rows = list_open_repairs(vault_root)
            print(f"Open repairs: {len(rows)}")
            for row in rows:
                print(
                    f"- {row.get('timestamp')} {row.get('source_relative_path')} -> {row.get('generated_relative_path')} ({row.get('detail')})"
                )
        if args.repair_run:
            open_count = run_repair(vault_root)
            print(f"Repair run completed. Open repair events recorded: {open_count}")

        if args.scan:
            for scanned_file in scan_vault_sources(vault_root):
                process_scanned_file(
                    connection=connection,
                    vault_id=vault_id,
                    scanned_file=scanned_file,
                    provider=provider,
                    config=config,
                    vault_root=vault_root,
                )
        if args.watch:
            run_watch_loop(
                connection=connection,
                vault_id=vault_id,
                vault_root=vault_root,
                provider=provider,
                config=config,
                watch_seconds=args.watch_seconds,
            )
        if args.dashboard:
            data = build_dashboard_data(
                connection=connection,
                config=config,
                vault_root=vault_root,
            )
            print(render_dashboard_text(data), end="")
        if args.ask:
            result = answer_question(
                connection=connection,
                vault_root=vault_root,
                question=args.ask,
            )
            print(render_qa_markdown(result), end="")

    return 0


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def process_markdown_or_text_if_supported(
    connection: sqlite3.Connection,
    file_id: str,
    scanned_file: ScannedFile,
    provider: LLMProvider,
    config: AppConfig,
    vault_root: Path,
) -> None:
    if scanned_file.extension not in {".md", ".txt"}:
        return
    set_file_status(connection, file_id=file_id, status=FILE_STATUS_PROCESSING)
    try:
        if scanned_file.extension == ".md":
            title, extracted_text, metadata = extract_markdown(scanned_file.path)
        else:
            title, extracted_text, metadata = extract_text(scanned_file.path)
        source_document_id = upsert_source_document(
            connection=connection,
            file_id=file_id,
            title=title,
            extracted_text=extracted_text,
            extraction_metadata=metadata,
        )
        chunks = chunk_text(extracted_text)
        replace_chunks(connection=connection, source_document_id=source_document_id, chunks=chunks)
        summary_body = provider.generate_text(
            system_prompt=source_summary_system_prompt(),
            user_prompt=source_summary_user_prompt(
                source_title=title,
                relative_source_path=scanned_file.relative_path.as_posix(),
                extracted_text=extracted_text,
            ),
        )
        summary_markdown = render_source_summary_page(
            source_title=title,
            relative_source_path=scanned_file.relative_path.as_posix(),
            summary_markdown_body=summary_body,
        )
        target_path = resolve_summary_target_path(vault_root=vault_root, source_title=title)
        atomic_write_markdown(target_path=target_path, content=summary_markdown, vault_root=vault_root)
        relative_generated_path = target_path.relative_to(vault_root).as_posix()
        content_hash = sha256_text(summary_markdown)
        upsert_generated_page(
            connection=connection,
            source_document_id=source_document_id,
            page_type="source_summary",
            path=target_path,
            relative_path=relative_generated_path,
            sha256=content_hash,
            status="generated",
        )
        try:
            layout = resolve_layout(vault_root)
            rebuild_index_page(
                index_path=layout.index_file,
                sources_dir=layout.sources_dir,
                vault_root=vault_root,
            )
            append_processing_log(
                processing_log_path=layout.processing_log_file,
                source_relative_path=scanned_file.relative_path.as_posix(),
                generated_relative_path=relative_generated_path,
            )
            append_audit_jsonl(
                audit_log_jsonl_path=layout.audit_dir / "audit-log.jsonl",
                event_type="generated_summary_written",
                source_path=scanned_file.relative_path.as_posix(),
                generated_path=relative_generated_path,
                model_provider=provider.provider_name(),
                model_name=config.model,
                content_hash=content_hash,
            )
            insert_audit_event(
                connection=connection,
                event_type="generated_summary_written",
                target_path=relative_generated_path,
                source_paths=[scanned_file.relative_path.as_posix()],
                summary=f"Generated summary for {scanned_file.relative_path.as_posix()}",
                details={
                    "provider": provider.provider_name(),
                    "model": config.model,
                    "content_hash": content_hash,
                },
            )
            set_file_status(connection, file_id=file_id, status=FILE_STATUS_GENERATED)
        except Exception as post_write_exc:  # noqa: BLE001
            append_repair_event(
                vault_root=vault_root,
                event_type="post_write_inconsistency",
                source_relative_path=scanned_file.relative_path.as_posix(),
                generated_relative_path=relative_generated_path,
                detail=str(post_write_exc),
            )
            set_file_status(
                connection,
                file_id=file_id,
                status=FILE_STATUS_FAILED_TRANSIENT,
                error_message=f"repair needed: {post_write_exc}",
            )
    except Exception as exc:  # noqa: BLE001
        set_file_status(
            connection,
            file_id=file_id,
            status=FILE_STATUS_FAILED_PERMANENT,
            error_message=f"ingestion failed: {exc}",
        )


def process_scanned_file(
    *,
    connection: sqlite3.Connection,
    vault_id: str,
    scanned_file: ScannedFile,
    provider: LLMProvider,
    config: AppConfig,
    vault_root: Path,
) -> None:
    digest = sha256_file(scanned_file.path)
    existing = get_file_by_relative_path(
        connection,
        vault_id=vault_id,
        relative_path=scanned_file.relative_path.as_posix(),
    )
    if existing and existing["sha256"] == digest:
        upsert_scanned_file(
            connection,
            vault_id=vault_id,
            scanned=scanned_file,
            sha256=digest,
            status=FILE_STATUS_SKIPPED_UNCHANGED,
        )
        return
    file_id = upsert_scanned_file(
        connection,
        vault_id=vault_id,
        scanned=scanned_file,
        sha256=digest,
        status=FILE_STATUS_DISCOVERED,
    )
    set_file_status(connection, file_id=file_id, status=FILE_STATUS_QUEUED)
    process_markdown_or_text_if_supported(
        connection=connection,
        file_id=file_id,
        scanned_file=scanned_file,
        provider=provider,
        config=config,
        vault_root=vault_root,
    )


def run_watch_loop(
    *,
    connection: sqlite3.Connection,
    vault_id: str,
    vault_root: Path,
    provider: LLMProvider,
    config: AppConfig,
    watch_seconds: float,
) -> None:
    settings = WatchSettings()
    work_queue: "queue.Queue[Path]" = queue.Queue()
    observer = start_observer(vault_root=vault_root, work_queue=work_queue)
    print("Watcher started. Press Ctrl+C to stop.")
    start_time = time.monotonic()
    try:
        while True:
            if watch_seconds > 0 and (time.monotonic() - start_time) >= watch_seconds:
                break
            changed_paths = drain_debounced_paths(work_queue, settings.debounce_seconds)
            for changed_path in changed_paths:
                if not wait_for_stable_file(changed_path, settings):
                    continue
                scanned_file = to_scanned_file(changed_path, vault_root)
                process_scanned_file(
                    connection=connection,
                    vault_id=vault_id,
                    scanned_file=scanned_file,
                    provider=provider,
                    config=config,
                    vault_root=vault_root,
                )
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join(timeout=5.0)


def build_provider(config: AppConfig) -> GroqProvider:
    if config.provider != "groq":
        raise ValueError(f"Unsupported provider '{config.provider}' for MVP-007")
    return GroqProvider.from_values(
        api_key=config.groq_api_key,
        model=config.model,
        base_url=config.groq_base_url,
    )


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def run_desktop_shell(vault_root: Path, config: AppConfig) -> int:
    try:
        from llm_wiki.ui.desktop_shell import run_desktop_app
    except Exception as exc:  # noqa: BLE001
        print(f"Desktop shell unavailable: {exc}")
        return 1
    return run_desktop_app(vault_root=vault_root, config=config)


def provider_ping(provider: LLMProvider) -> tuple[bool, float, str]:
    ping_fn = getattr(provider, "ping", None)
    if ping_fn is None:
        raise ValueError(f"Provider '{provider.provider_name()}' does not support ping")
    result = ping_fn()
    return result


if __name__ == "__main__":
    from llm_wiki.gui_app import main as gui_main

    raise SystemExit(gui_main())
