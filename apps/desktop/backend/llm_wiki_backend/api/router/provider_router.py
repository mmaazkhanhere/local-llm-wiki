from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.core.config import load_config
from llm_wiki_backend.core.errors import VaultValidationError
from llm_wiki_backend.core.models import (
    AppConfig,
    ProviderStatusResponse,
    ProviderTestRequest,
    ProviderTestResponse,
)
from llm_wiki_backend.llm.groq import test_groq_connection
from llm_wiki_backend.security.secrets import has_groq_key, save_groq_key
from llm_wiki_backend.vault.service import validate_vault

router = APIRouter(prefix="/provider", tags=["Provider"])


@router.post("/groq/test", response_model=ProviderTestResponse, description="Test Groq API key and persist on success")
def provider_test(request: ProviderTestRequest, vault_path: str) -> ProviderTestResponse:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    connected, message = test_groq_connection(request.api_key)
    if connected:
        save_groq_key(vault, request.api_key)
    return ProviderTestResponse(connected=connected, message=message)


@router.get("/groq/status", response_model=ProviderStatusResponse, description="Get Groq provider configuration and model settings")
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
