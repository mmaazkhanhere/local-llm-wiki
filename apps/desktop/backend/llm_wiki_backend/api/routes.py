from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.core.config import load_config, save_config
from llm_wiki_backend.core.errors import ConfigError, VaultValidationError
from llm_wiki_backend.core.models import (
    AppConfig,
    BootstrapResponse,
    ConfigureVaultResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    SelectVaultRequest,
    SelectVaultResponse,
    StatusResponse,
)
from llm_wiki_backend.db.service import initialize_database
from llm_wiki_backend.llm.groq import test_groq_connection
from llm_wiki_backend.security.secrets import save_groq_key
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
