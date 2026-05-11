from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


LintStatus = Literal["clean", "warnings", "needs_review", "mechanical_errors", "lint_failed"]
LintSeverity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class LintRunSummary:
    lint_run_id: str
    ingest_run_id: str | None
    status: LintStatus
    mechanical_issue_count: int
    semantic_issue_count: int
    fixes_applied_count: int
    review_pages_created_count: int
    started_at: str
    finished_at: str | None = None
    error_message: str | None = None


class SemanticLintIssue(BaseModel):
    issue_type: str = Field(min_length=1)
    severity: LintSeverity
    affected_pages: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)


class SemanticLintResult(BaseModel):
    issues: list[SemanticLintIssue] = Field(default_factory=list)
