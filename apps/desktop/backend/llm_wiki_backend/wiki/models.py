from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from llm_wiki_backend.core.errors import LLMOutputError


class SourceCitation(BaseModel):
    locator: str = Field(min_length=1)


class WikiCandidate(BaseModel):
    page_type: Literal["concept", "entity", "comparison", "map"]
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    content_markdown: str = Field(min_length=1)
    wiki_links: list[str] = Field(default_factory=list)
    sources: list[SourceCitation] = Field(min_length=1)


class FlashcardCandidate(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    sources: list[SourceCitation] = Field(min_length=1)


class WikiGenerationPlan(BaseModel):
    candidates: list[WikiCandidate] = Field(default_factory=list)
    flashcards: list[FlashcardCandidate] = Field(default_factory=list)


class WikiCandidatePreview(BaseModel):
    page_type: str
    title: str
    summary: str
    target_path: str


class WikiSourceResult(BaseModel):
    source_path: str
    status: Literal["generated", "skipped", "failed"]
    candidates: list[WikiCandidatePreview] = Field(default_factory=list)
    generated_page_paths: list[str] = Field(default_factory=list)
    skipped_titles: list[str] = Field(default_factory=list)
    flashcard_path: str | None = None
    index_updated: bool = False
    log_updated: bool = False
    error_message: str | None = None


class WikiGenerationSummary(BaseModel):
    attempted_source_count: int = 0
    processed_source_count: int = 0
    failed_count: int = 0
    generated_page_count: int = 0
    generated_flashcard_count: int = 0
    source_results: list[WikiSourceResult] = Field(default_factory=list)
    skipped_reason: str | None = None


def parse_generation_plan(payload: Any) -> WikiGenerationPlan:
    raw_payload = payload
    if isinstance(payload, str):
        try:
            raw_payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LLMOutputError("LLM returned invalid JSON for wiki generation.") from exc
    try:
        return WikiGenerationPlan.model_validate(raw_payload)
    except ValidationError as exc:
        raise LLMOutputError("LLM returned an invalid wiki generation plan.") from exc


def generation_plan_schema() -> dict[str, Any]:
    return WikiGenerationPlan.model_json_schema()
