from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.core.config import load_config, save_config
from llm_wiki_backend.core.errors import ConfigError, VaultValidationError
from llm_wiki_backend.core.models import (
    AppConfig,
    BootstrapResponse,
    ConfigureVaultResponse,
    IngestFileResponse,
    IngestSummaryResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderStatusResponse,
    RawInboxResponse,
    SelectVaultRequest,
    SelectVaultResponse,
    StatusResponse,
    WatcherStatusResponse,
)
from llm_wiki_backend.db.service import initialize_database
from llm_wiki_backend.ingestion.service import (
    hash_discovered_files,
    ingest_raw_files,
    list_raw_inbox,
    process_queued_files,
    scan_raw_files,
)
from llm_wiki_backend.ingestion.watcher import RAW_WATCHER
from llm_wiki_backend.llm.groq import test_groq_connection
from llm_wiki_backend.security.secrets import save_groq_key
from llm_wiki_backend.security.secrets import has_groq_key
from llm_wiki_backend.vault.service import (
    create_required_directories,
    create_wiki_index_files,
    detect_git,
    detect_obsidian_cli,
    validate_vault,
)

router = APIRouter()


@router.post("/vault/select", response_model=SelectVaultResponse)
def select_vault(request: SelectVaultRequest) -> SelectVaultResponse:
    try:
        vault_path, has_obsidian = validate_vault(request.path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    warning = None
    if not has_obsidian:
        warning = ".obsidian/ not found. Continuing is allowed, but this may not be an Obsidian vault yet."
    return SelectVaultResponse(
        vault_path=str(vault_path),
        exists=vault_path.exists(),
        is_directory=vault_path.is_dir(),
        has_obsidian=has_obsidian,
        warning=warning,
    )


@router.post("/vault/configure", response_model=ConfigureVaultResponse)
def configure_vault(request: SelectVaultRequest) -> ConfigureVaultResponse:
    try:
        vault_path, has_obsidian = validate_vault(request.path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    config = AppConfig(vault_path=str(vault_path))
    save_config(config, vault_path)
    warning = None
    if not has_obsidian:
        warning = ".obsidian/ not found. Continuing is allowed."
    return ConfigureVaultResponse(
        vault_path=str(vault_path),
        has_obsidian=has_obsidian,
        git_detected=detect_git(vault_path),
        obsidian_cli_available=detect_obsidian_cli(),
        warning=warning,
    )


@router.post("/vault/bootstrap", response_model=BootstrapResponse)
def bootstrap_vault(request: SelectVaultRequest) -> BootstrapResponse:
    try:
        vault_path, _ = validate_vault(request.path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    created_dirs = create_required_directories(vault_path)
    created_files = create_wiki_index_files(vault_path)
    db_path = initialize_database(vault_path)
    config = load_config(vault_path) or AppConfig(vault_path=str(vault_path))
    config_path = save_config(config, vault_path)
    return BootstrapResponse(
        vault_path=str(vault_path),
        created_directories=created_dirs,
        created_files=created_files,
        database_path=str(db_path),
        config_path=str(config_path),
    )


@router.get("/vault/status", response_model=StatusResponse)
def vault_status(vault_path: str) -> StatusResponse:
    try:
        vault, has_obsidian = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StatusResponse(
        vault_path=str(vault),
        has_obsidian=has_obsidian,
        git_detected=detect_git(vault),
        obsidian_cli_available=detect_obsidian_cli(),
    )


@router.post("/provider/groq/test", response_model=ProviderTestResponse)
def provider_test(request: ProviderTestRequest, vault_path: str) -> ProviderTestResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connected, message = test_groq_connection(request.api_key)
    if connected:
        save_groq_key(vault, request.api_key)
    return ProviderTestResponse(connected=connected, message=message)


@router.get("/provider/groq/status", response_model=ProviderStatusResponse)
def provider_status(vault_path: str) -> ProviderStatusResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = load_config(vault) or AppConfig(vault_path=str(vault))
    configured = has_groq_key(vault)
    message = "Groq key configured." if configured else "Groq key not configured."
    return ProviderStatusResponse(
        configured=configured,
        connected=configured,
        message=message,
        default_text_model=config.provider.default_text_model,
        cheap_fast_model=config.provider.cheap_fast_model,
        review_model=config.provider.review_model,
        vision_model=config.provider.vision_model,
    )


@router.post("/ingest/raw/scan", response_model=IngestSummaryResponse)
def raw_scan(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = scan_raw_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/ingest/raw/hash", response_model=IngestSummaryResponse)
def raw_hash(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = hash_discovered_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/ingest/raw/process", response_model=IngestSummaryResponse)
def raw_process(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = process_queued_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.post("/ingest/raw/run", response_model=IngestSummaryResponse)
def raw_run(vault_path: str) -> IngestSummaryResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = ingest_raw_files(vault)
    return IngestSummaryResponse(**summary.__dict__)


@router.get("/ingest/raw/inbox", response_model=RawInboxResponse)
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


@router.post("/ingest/raw/watch/start", response_model=WatcherStatusResponse)
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


@router.post("/ingest/raw/watch/stop", response_model=WatcherStatusResponse)
def raw_watch_stop() -> WatcherStatusResponse:
    RAW_WATCHER.stop()
    status = RAW_WATCHER.status()
    return WatcherStatusResponse(**status.__dict__)


@router.get("/ingest/raw/watch/status", response_model=WatcherStatusResponse)
def raw_watch_status() -> WatcherStatusResponse:
    status = RAW_WATCHER.status()
    return WatcherStatusResponse(**status.__dict__)
