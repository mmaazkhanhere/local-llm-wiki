from __future__ import annotations

from fastapi import APIRouter, HTTPException

from llm_wiki_backend.core.errors import VaultValidationError, WikiGenerationError
from llm_wiki_backend.core.models import (
    ApproveAllResponse,
    EditProposalRequest,
    ReviewProposalListResponse,
    ReviewProposalResponse,
)
from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.vault.service import validate_vault
from llm_wiki_backend.wiki.review_service import (
    approve_all_for_source,
    approve_proposal,
    edit_proposal,
    get_proposal,
    list_proposals,
    reject_proposal,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("", response_model=ReviewProposalListResponse)
def review_list(vault_path: str, status: str = "pending") -> ReviewProposalListResponse:
    vault = _validated_vault(vault_path)
    with connect_database(vault) as conn:
        proposals = list_proposals(conn, status=status)
    return ReviewProposalListResponse(proposals=[ReviewProposalResponse(**item) for item in proposals])


@router.get("/{proposal_id}", response_model=ReviewProposalResponse)
def review_get(proposal_id: str, vault_path: str) -> ReviewProposalResponse:
    vault = _validated_vault(vault_path)
    with connect_database(vault) as conn:
        proposal = get_proposal(conn, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return ReviewProposalResponse(**proposal)


@router.put("/{proposal_id}", response_model=ReviewProposalResponse)
def review_edit(proposal_id: str, request: EditProposalRequest, vault_path: str) -> ReviewProposalResponse:
    vault = _validated_vault(vault_path)
    try:
        with connect_database(vault) as conn:
            payload = edit_proposal(conn, vault_path=vault, proposal_id=proposal_id, proposed_content=request.proposed_content)
            conn.commit()
    except WikiGenerationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewProposalResponse(**payload)


@router.post("/{proposal_id}/approve", response_model=ReviewProposalResponse)
def review_approve(proposal_id: str, vault_path: str) -> ReviewProposalResponse:
    vault = _validated_vault(vault_path)
    try:
        with connect_database(vault) as conn:
            payload = approve_proposal(conn, vault_path=vault, proposal_id=proposal_id)
            conn.commit()
    except WikiGenerationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewProposalResponse(**payload)


@router.post("/{proposal_id}/reject", response_model=ReviewProposalResponse)
def review_reject(proposal_id: str, vault_path: str) -> ReviewProposalResponse:
    vault = _validated_vault(vault_path)
    try:
        with connect_database(vault) as conn:
            payload = reject_proposal(conn, vault_path=vault, proposal_id=proposal_id)
            conn.commit()
    except WikiGenerationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewProposalResponse(**payload)


@router.post("/approve-all", response_model=ApproveAllResponse)
def review_approve_all(vault_path: str, source_relative_path: str) -> ApproveAllResponse:
    vault = _validated_vault(vault_path)
    with connect_database(vault) as conn:
        payload = approve_all_for_source(conn, vault_path=vault, source_relative_path=source_relative_path)
        conn.commit()
    return ApproveAllResponse(**payload)


def _validated_vault(vault_path: str):
    try:
        vault, _ = validate_vault(vault_path)
        return vault
    except VaultValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
