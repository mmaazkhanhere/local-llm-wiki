from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.core.errors import VaultValidationError
from llm_wiki_backend.lint.service import (
    apply_safe_fixes,
    create_semantic_review_pages,
    latest_lint_status,
    run_post_ingest_smoke_lint,
    run_semantic_lint,
)
from llm_wiki_backend.vault.service import validate_vault

router = APIRouter(prefix="/lint", tags=["Lint"])


@router.get("/latest", description="Get latest lint run summary for the vault")
def lint_latest(vault_path: str) -> dict:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    latest = latest_lint_status(vault_path=vault)
    return {"latest": latest.__dict__ if latest else None}


@router.post("/run", description="Run lint for the vault (manual trigger)")
def lint_run(vault_path: str, ingest_run_id: str | None = None, semantic: bool = False) -> dict:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = run_post_ingest_smoke_lint(vault_path=vault, ingest_run_id=ingest_run_id)
    semantic_count = 0
    if semantic:
        semantic_count = run_semantic_lint(vault_path=vault, lint_run_id=result.lint_run_id)
    refreshed = latest_lint_status(vault_path=vault) or result
    payload = refreshed.__dict__.copy()
    payload["semantic_recorded_count"] = semantic_count
    return {"result": payload}


@router.post("/fix/apply", description="Apply safe mechanical auto-fixes for a given lint run")
def lint_fix_apply(vault_path: str, lint_run_id: str, dry_run: bool = True) -> dict:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = apply_safe_fixes(vault_path=vault, lint_run_id=lint_run_id, dry_run=dry_run)
    return payload


@router.post("/reviews/create", description="Create Review pages for semantic lint issues")
def lint_reviews_create(vault_path: str, lint_run_id: str) -> dict:
    try:
        vault, _ = validate_vault(vault_path)
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    created = create_semantic_review_pages(vault_path=vault, lint_run_id=lint_run_id)
    return {"created": created}
