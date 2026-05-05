from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    heading: str | None = None
    page_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None


@dataclass(frozen=True)
class ExtractionDraft:
    title: str | None
    text: str
    metadata: dict[str, object]
    chunks: list[ChunkDraft]
    limited: bool = False


@dataclass(frozen=True)
class FileSnapshot:
    path: str
    relative_path: str
    file_type: str
    size_bytes: int
    modified_at: str
    created_at: str
    processing_status: str
    error_message: str | None
    sha256: str


@dataclass(frozen=True)
class ProcessSummary:
    discovered_count: int = 0
    queued_count: int = 0
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    pending_image_count: int = 0
