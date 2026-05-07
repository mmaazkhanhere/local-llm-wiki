from __future__ import annotations

from fastapi import APIRouter

from llm_wiki_backend.api.router.ingest_router import router as ingest_api_router
from llm_wiki_backend.api.router.provider_router import router as provider_api_router
from llm_wiki_backend.api.router.vault_router import router as vault_api_router

api_router = APIRouter()
api_router.include_router(vault_api_router)
api_router.include_router(provider_api_router)
api_router.include_router(ingest_api_router)

__all__ = ["api_router"]
