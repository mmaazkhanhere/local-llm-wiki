from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    timestamp: str

    @classmethod
    def ok(cls, version: str) -> "HealthResponse":
        return cls(status="ok", version=version, timestamp=datetime.now(UTC).isoformat())


class SelectVaultRequest(BaseModel):
    path: str = Field(min_length=1)


class SelectVaultResponse(BaseModel):
    vault_path: str
    exists: bool
    is_directory: bool
    has_obsidian: bool
    warning: str | None = None


class BootstrapResponse(BaseModel):
    vault_path: str
    created_directories: list[str]
    created_files: list[str]
    database_path: str
    config_path: str


class ResetVaultResponse(BaseModel):
    vault_path: str
    removed_paths: list[str]
    created_directories: list[str]
    created_files: list[str]
    config_path: str


class ProviderSettings(BaseModel):
    provider: str = "groq"
    default_text_model: str = "openai/gpt-oss-120b"
    cheap_fast_model: str = "llama-3.1-8b-instant"
    review_model: str = "openai/gpt-oss-120b"
    vision_model: str | None = None


class AppConfig(BaseModel):
    vault_path: str
    provider: ProviderSettings = Field(default_factory=ProviderSettings)


class ConfigureVaultResponse(BaseModel):
    vault_path: str
    has_obsidian: bool
    git_detected: bool
    obsidian_cli_available: bool
    warning: str | None = None


class ProviderTestRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ProviderTestResponse(BaseModel):
    provider: str = "groq"
    connected: bool
    message: str


class ProviderStatusResponse(BaseModel):
    provider: str = "groq"
    configured: bool
    connected: bool
    message: str
    default_text_model: str
    cheap_fast_model: str
    review_model: str
    vision_model: str | None = None


class WikiCandidateGroupResponse(BaseModel):
    concepts: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    maps: list[str] = Field(default_factory=list)
    flashcards: list[str] = Field(default_factory=list)


class WikiGenerationSourceResponse(BaseModel):
    relative_path: str
    status: str
    generated_pages: list[str] = Field(default_factory=list)
    flashcard_files: list[str] = Field(default_factory=list)
    candidates: WikiCandidateGroupResponse = Field(default_factory=WikiCandidateGroupResponse)
    error_message: str | None = None


class WikiGenerationSummaryResponse(BaseModel):
    sources_processed_count: int = 0
    candidate_count: int = 0
    pages_created_count: int = 0
    flashcard_files_created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    sources: list[WikiGenerationSourceResponse] = Field(default_factory=list)


class StatusResponse(BaseModel):
    vault_path: str
    has_obsidian: bool
    git_detected: bool
    obsidian_cli_available: bool


class IngestFileResponse(BaseModel):
    path: str
    relative_path: str
    file_type: str
    size_bytes: int
    modified_at: str
    created_at: str
    processing_status: str
    error_message: str | None = None
    sha256: str


class IngestSummaryResponse(BaseModel):
    discovered_count: int = 0
    queued_count: int = 0
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    pending_image_count: int = 0
    unsupported_count: int = 0
    wiki_generation: WikiGenerationSummaryResponse | None = None


class RawInboxResponse(BaseModel):
    summary: IngestSummaryResponse
    files: list[IngestFileResponse]


class WatcherStatusResponse(BaseModel):
    running: bool
    vault_path: str | None = None
    poll_interval_seconds: float
    stabilize_seconds: float
