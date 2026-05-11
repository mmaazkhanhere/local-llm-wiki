from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.ask.service import ask_question, create_proposed_update_from_answer
from llm_wiki_backend.core.errors import LLMOutputError, VaultValidationError, WikiGenerationError
from llm_wiki_backend.core.models import AskProposeRequest, AskRequest, AskResponse
from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.vault.service import validate_vault

router = APIRouter(prefix="/ask", tags=["Ask"])


@router.post("/query", response_model=AskResponse)
def ask_query(request: AskRequest, vault_path: str) -> AskResponse:
    vault = _validated_vault(vault_path)
    try:
        with connect_database(vault) as conn:
            payload = ask_question(conn, vault_path=vault, question=request.question)
    except (WikiGenerationError, LLMOutputError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AskResponse(**payload)


@router.post("/propose-update")
def ask_propose_update(request: AskProposeRequest, vault_path: str) -> dict:
    vault = _validated_vault(vault_path)
    try:
        with connect_database(vault) as conn:
            payload = create_proposed_update_from_answer(
                conn,
                vault_path=vault,
                question=request.question,
                answer=request.answer,
                target_relative_path=request.target_relative_path,
                target_title=request.target_title,
                reason=request.reason,
                source_citations=request.source_citations,
            )
            conn.commit()
    except WikiGenerationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return payload


def _validated_vault(vault_path: str):
    try:
        vault, _ = validate_vault(vault_path)
        return vault
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
