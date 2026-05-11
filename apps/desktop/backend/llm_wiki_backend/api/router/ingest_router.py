from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.core.errors import VaultValidationError
from llm_wiki_backend.core.models import (
    IngestFileResponse,
    IngestSummaryResponse,
    RawInboxResponse,
    WatcherStatusResponse,
)
from llm_wiki_backend.ingestion.service import (
    hash_discovered_files,
    ingest_raw_files,
    list_raw_inbox,
    process_queued_files,
    scan_raw_files,
)
from llm_wiki_backend.lint.service import run_post_ingest_smoke_lint
from llm_wiki_backend.ingestion.watcher import RAW_WATCHER
from llm_wiki_backend.vault.service import validate_vault
from llm_wiki_backend.wiki.service import generate_wiki_for_pending_sources

router = APIRouter(prefix="/ingest", tags=["Ingest"])


@router.post("/raw/scan", response_model=IngestSummaryResponse, description="Scan Raw/ for new files and persist discovery state")
def raw_scan(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = scan_raw_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/raw/hash", response_model=IngestSummaryResponse, description="Compute hashes and queue reprocessing when content changes")
def raw_hash(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = hash_discovered_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.post(
    "/raw/process",
    response_model=IngestSummaryResponse,
    description="Process queued files (extract/chunk) and generate new wiki pages",
)
def raw_process(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    import uuid

    ingest_run_id = str(uuid.uuid4())
    summary = process_queued_files(vault)
    wiki_summary = generate_wiki_for_pending_sources(vault, ingest_run_id=ingest_run_id)
    lint_summary = run_post_ingest_smoke_lint(vault_path=vault, ingest_run_id=ingest_run_id)
    payload = summary.__dict__.copy()
    payload["ingest_run_id"] = ingest_run_id
    payload["failed_count"] = summary.failed_count + wiki_summary.failed_count
    payload["wiki_generation"] = wiki_summary.model_dump()
    payload["lint"] = lint_summary.__dict__
    return IngestSummaryResponse(**payload)


@router.post("/raw/run", response_model=IngestSummaryResponse, description="Run scan + hash + process as one operation")
def raw_run(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = ingest_raw_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.get("/raw/inbox", response_model=RawInboxResponse, description="List Raw Inbox file processing statuses")
def raw_inbox(vault_path: str) -> RawInboxResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    files = list_raw_inbox(vault)
    return RawInboxResponse(
        summary=IngestSummaryResponse(
            discovered_count=len(files),
            queued_count=sum(1 for item in files if item.processing_status == "queued"),
            processed_count=sum(1 for item in files if item.processing_status == "processed"),
            skipped_count=sum(1 for item in files if item.processing_status == "skipped_unchanged"),
            failed_count=sum(1 for item in files if item.processing_status.startswith("failed")),
            pending_image_count=sum(1 for item in files if item.processing_status == "pending_image"),
        ),
        files=[IngestFileResponse(**item.__dict__) for item in files],
    )


@router.post("/raw/watch/start", response_model=WatcherStatusResponse, description="Start watching Raw/ for changes and auto-ingest")
def raw_watch_start(
    vault_path: str,
    poll_interval_seconds: float = 1.0,
    stabilize_seconds: float = 0.8,
) -> WatcherStatusResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    RAW_WATCHER.start(vault, poll_interval_seconds=poll_interval_seconds, stabilize_seconds=stabilize_seconds)
    status = RAW_WATCHER.status()
    return WatcherStatusResponse(**status.__dict__)


@router.post("/raw/watch/stop", response_model=WatcherStatusResponse, description="Stop the Raw/ watcher")
def raw_watch_stop() -> WatcherStatusResponse:
    RAW_WATCHER.stop()
    status = RAW_WATCHER.status()
    return WatcherStatusResponse(**status.__dict__)


@router.get("/raw/watch/status", response_model=WatcherStatusResponse, description="Get Raw/ watcher status")
def raw_watch_status() -> WatcherStatusResponse:
    status = RAW_WATCHER.status()
    return WatcherStatusResponse(**status.__dict__)
