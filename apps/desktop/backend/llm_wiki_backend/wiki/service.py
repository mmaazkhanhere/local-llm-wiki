from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from llm_wiki_backend.core.config import load_config
from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.llm.groq import generate_candidate_response

PAGE_DIRECTORY_BY_TYPE = {
    "concept": Path("Wiki/Concepts"),
    "entity": Path("Wiki/Entities"),
    "comparison": Path("Wiki/Comparisons"),
    "map": Path("Wiki/Maps"),
}
INDEX_SECTION_BY_TYPE = {
    "concept": "## Concepts",
    "entity": "## Entities",
    "comparison": "## Comparisons",
    "map": "## Maps",
}
ALLOWED_WRITE_ROOTS = {Path("Wiki"), Path(".llm-wiki")}


class PageCandidate(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    body: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)
    why_it_matters: str | None = None
    how_it_works: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    index_group: str | None = None


class FlashcardCandidate(BaseModel):
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    related_pages: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)


class CandidatePayload(BaseModel):
    concepts: list[PageCandidate] = Field(default_factory=list)
    entities: list[PageCandidate] = Field(default_factory=list)
    comparisons: list[PageCandidate] = Field(default_factory=list)
    maps: list[PageCandidate] = Field(default_factory=list)
    flashcards: list[FlashcardCandidate] = Field(default_factory=list)


@dataclass(frozen=True)
class WikiSourceResult:
    relative_path: str
    status: str
    generated_pages: list[str]
    flashcard_files: list[str]
    candidates: dict[str, list[str]]
    error_message: str | None = None


@dataclass(frozen=True)
class WikiGenerationSummary:
    sources_processed_count: int = 0
    candidate_count: int = 0
    pages_created_count: int = 0
    flashcard_files_created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    sources: list[WikiSourceResult] | None = None


def parse_candidate_response(payload_text: str) -> CandidatePayload:
    normalized = payload_text.strip()
    if normalized.startswith("```"):
        normalized = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", normalized)
        normalized = re.sub(r"\s*```$", "", normalized)
    try:
        payload = json.loads(normalized)
        return CandidatePayload.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("Invalid LLM candidate payload.") from exc


def generate_wiki_for_pending_extractions(vault_path: Path) -> WikiGenerationSummary:
    config = load_config(vault_path)
    model_id = config.provider.default_text_model if config is not None else "openai/gpt-oss-120b"
    pending_rows = _list_pending_extractions(vault_path)
    if not pending_rows:
        return WikiGenerationSummary(sources=[])

    results: list[WikiSourceResult] = []
    candidate_count = 0
    pages_created_count = 0
    flashcard_files_created_count = 0
    skipped_count = 0
    failed_count = 0

    for row in pending_rows:
        relative_path = str(row["relative_path"])
        try:
            payload_text = generate_candidate_response(
                vault_path=vault_path,
                model_id=model_id,
                source_title=str(row["title"] or Path(relative_path).stem),
                relative_path=relative_path,
                extracted_text=str(row["extracted_text"] or ""),
            )
            payload = parse_candidate_response(payload_text)
            created_pages, created_flashcards = _write_candidate_artifacts(
                vault_path=vault_path,
                extraction_row=row,
                payload=payload,
            )
            source_result = WikiSourceResult(
                relative_path=relative_path,
                status="generated",
                generated_pages=created_pages,
                flashcard_files=created_flashcards,
                candidates=_candidate_titles(payload),
            )
            results.append(source_result)
            created_count = len(created_pages) + len(created_flashcards)
            candidate_count += _payload_candidate_count(payload)
            pages_created_count += len(created_pages)
            flashcard_files_created_count += len(created_flashcards)
            if created_count == 0:
                skipped_count += 1
            _record_audit_event(
                vault_path=vault_path,
                event_type="wiki_generation_completed",
                target_path=None,
                source_paths=[relative_path],
                summary=f"Generated wiki artifacts for {relative_path}",
                details={
                    "relative_path": relative_path,
                    "generated_pages": created_pages,
                    "flashcard_files": created_flashcards,
                    "candidates": _candidate_titles(payload),
                },
            )
        except Exception as exc:
            failed_count += 1
            results.append(
                WikiSourceResult(
                    relative_path=relative_path,
                    status="failed",
                    generated_pages=[],
                    flashcard_files=[],
                    candidates={"concepts": [], "entities": [], "comparisons": [], "maps": [], "flashcards": []},
                    error_message=str(exc),
                )
            )
            _record_audit_event(
                vault_path=vault_path,
                event_type="wiki_generation_failed",
                target_path=None,
                source_paths=[relative_path],
                summary=f"Failed wiki generation for {relative_path}",
                details={"error": str(exc)},
            )

    return WikiGenerationSummary(
        sources_processed_count=len(results),
        candidate_count=candidate_count,
        pages_created_count=pages_created_count,
        flashcard_files_created_count=flashcard_files_created_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        sources=results,
    )
def _list_pending_extractions(vault_path: Path) -> list[sqlite3.Row]:
    with connect_database(vault_path) as conn:
        rows = conn.execute(
            """
            SELECT
              e.id AS extraction_id,
              e.title AS title,
              e.extracted_text AS extracted_text,
              f.id AS file_id,
              f.relative_path AS relative_path
            FROM extractions e
            JOIN files f ON f.id = e.file_id
            WHERE f.vault_id = ?
              AND f.processing_status IN ('processed', 'extraction_limited', 'skipped_unchanged')
            ORDER BY f.relative_path ASC
            """,
            (_vault_id(vault_path),),
        ).fetchall()

        pending: list[sqlite3.Row] = []
        for row in rows:
            if _needs_wiki_regeneration(conn, vault_path=vault_path, row=row):
                pending.append(row)
        return pending


def _needs_wiki_regeneration(conn: sqlite3.Connection, *, vault_path: Path, row: sqlite3.Row) -> bool:
    source_paths_json = json.dumps([str(row["relative_path"])])
    completed = conn.execute(
        """
        SELECT details_json
        FROM audit_events
        WHERE event_type = 'wiki_generation_completed' AND source_paths_json = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (source_paths_json,),
    ).fetchone()
    if completed is None:
        return True

    try:
        details = json.loads(str(completed["details_json"] or "{}"))
    except json.JSONDecodeError:
        return True

    generated_pages = details.get("generated_pages", [])
    flashcard_files = details.get("flashcard_files", [])
    for relative in generated_pages + flashcard_files:
        if not isinstance(relative, str) or not relative.strip():
            continue
        if not (vault_path / relative).exists():
            return True
    return False


def _write_candidate_artifacts(vault_path: Path, extraction_row: sqlite3.Row, payload: CandidatePayload) -> tuple[list[str], list[str]]:
    relative_path = str(extraction_row["relative_path"])
    extraction_id = str(extraction_row["extraction_id"])
    created_pages: list[str] = []
    created_flashcards: list[str] = []
    index_entries: list[tuple[str, str, str]] = []

    with connect_database(vault_path) as conn:
        for page_type, candidates in (
            ("concept", payload.concepts),
            ("entity", payload.entities),
            ("comparison", payload.comparisons),
            ("map", payload.maps),
        ):
            seen_titles: set[str] = set()
            for candidate in candidates:
                canonical_title = _canonical_wiki_title(candidate.title)
                if not canonical_title:
                    continue
                if canonical_title.lower() in seen_titles:
                    continue
                seen_titles.add(canonical_title.lower())
                if not _should_create_page(page_type=page_type, candidate=candidate):
                    continue

                target_rel = _page_target_relative(page_type, canonical_title)
                if target_rel is None:
                    continue

                target_path = vault_path / target_rel
                if target_path.exists():
                    continue

                markdown = _render_page_markdown(page_type, candidate, canonical_title, relative_path)
                _atomic_write_text(vault_path, target_path, markdown)
                _insert_wiki_page_row(
                    conn,
                    extraction_id=extraction_id,
                    page_type=page_type,
                    target_path=target_path,
                    relative_path=target_rel.as_posix(),
                    markdown=markdown,
                )
                created_pages.append(target_rel.as_posix())
                index_entries.append((page_type, canonical_title, candidate.summary.strip()))
                _record_audit_event(
                    vault_path=vault_path,
                    event_type="wiki_page_created",
                    target_path=target_rel.as_posix(),
                    source_paths=[relative_path],
                    summary=f"Created {page_type} page {canonical_title}",
                    details={"page_type": page_type, "title": canonical_title},
                    conn=conn,
                )

        flashcards_rel = _flashcards_target_relative(payload.flashcards)
        if flashcards_rel is not None and not (vault_path / flashcards_rel).exists():
            markdown = _render_flashcards_markdown(payload.flashcards, relative_path)
            _atomic_write_text(vault_path, vault_path / flashcards_rel, markdown)
            created_flashcards.append(flashcards_rel.as_posix())
            for candidate in payload.flashcards:
                conn.execute(
                    """
                    INSERT INTO flashcards(id, extraction_id, question, answer, created_at)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), extraction_id, candidate.question.strip(), candidate.answer.strip(), _now_iso()),
                )
            _record_audit_event(
                vault_path=vault_path,
                event_type="flashcards_created",
                target_path=flashcards_rel.as_posix(),
                source_paths=[relative_path],
                summary=f"Created flashcards for {relative_path}",
                details={"count": len(payload.flashcards)},
                conn=conn,
            )

        if index_entries:
            index_rel = Path("Wiki/index.md")
            index_path = vault_path / index_rel
            updated_index = _update_index_text(index_path.read_text(encoding="utf-8"), index_entries)
            _atomic_write_text(vault_path, index_path, updated_index)
            _record_audit_event(
                vault_path=vault_path,
                event_type="wiki_index_updated",
                target_path=index_rel.as_posix(),
                source_paths=[relative_path],
                summary=f"Updated wiki index for {relative_path}",
                details={"entries_added": [title for _, title, _ in index_entries]},
                conn=conn,
            )

        if created_pages or created_flashcards:
            log_rel = Path("Wiki/log.md")
            log_path = vault_path / log_rel
            updated_log = _append_log_entry(
                log_path.read_text(encoding="utf-8"),
                relative_path=relative_path,
                generated_pages=created_pages,
                flashcard_files=created_flashcards,
            )
            _atomic_write_text(vault_path, log_path, updated_log)
            _record_audit_event(
                vault_path=vault_path,
                event_type="wiki_log_appended",
                target_path=log_rel.as_posix(),
                source_paths=[relative_path],
                summary=f"Appended wiki log entry for {relative_path}",
                details={"generated_pages": created_pages, "flashcard_files": created_flashcards},
                conn=conn,
            )

        conn.commit()

    return created_pages, created_flashcards


def _page_target_relative(page_type: str, title: str) -> Path | None:
    safe_stem = _sanitize_filename(title)
    if not safe_stem:
        return None
    return PAGE_DIRECTORY_BY_TYPE[page_type] / f"{safe_stem}.md"


def _flashcards_target_relative(candidates: list[FlashcardCandidate]) -> Path | None:
    if not candidates:
        return None
    safe_stem = _sanitize_filename(candidates[0].title.strip())
    if not safe_stem:
        return None
    return Path("Wiki/Flashcards") / f"{safe_stem}.md"


def _render_page_markdown(page_type: str, candidate: PageCandidate, canonical_title: str, relative_path: str) -> str:
    if page_type == "concept":
        return _render_concept_markdown(candidate, canonical_title, relative_path)
    lines = [f"# {canonical_title}", "", candidate.summary.strip()]
    body_lines = [line.strip() for line in candidate.body if line.strip()]
    if page_type == "comparison":
        lines.extend(["", "## Decision Context", "", candidate.summary.strip()])
        lines.extend(["", "## Tradeoffs", ""])
        lines.extend(_expand_body_lines(body_lines))
    elif body_lines:
        lines.extend(["", "## Notes", ""])
        lines.extend(_expand_body_lines(body_lines))
    links = [_canonical_wiki_title(link) for link in candidate.links if _canonical_wiki_title(link)]
    if links:
        lines.extend(["", "## Related", ""])
        for link in links:
            lines.append(f"- [[{link}]]")
    lines.extend(["", "## Sources", ""])
    for source_line in _source_lines(relative_path, candidate.source_notes):
        lines.append(f"- {source_line}")
    lines.append("")
    return "\n".join(lines)


def _render_concept_markdown(candidate: PageCandidate, canonical_title: str, relative_path: str) -> str:
    why_it_matters = (candidate.why_it_matters or "").strip()
    how_it_works = _clean_lines(candidate.how_it_works) or _clean_lines(candidate.body)
    examples = _clean_lines(candidate.examples) or _extract_examples(candidate.body)
    use_cases = _clean_lines(candidate.use_cases)
    failure_modes = _clean_lines(candidate.failure_modes)
    links = [_canonical_wiki_title(link) for link in candidate.links if _canonical_wiki_title(link)]

    lines = [
        f"# {canonical_title}",
        "",
        "## Definition",
        "",
        candidate.summary.strip(),
        "",
        "## Why It Matters",
        "",
        why_it_matters or "Improves retrieval and reuse across related technical notes.",
        "",
        "## How It Works",
        "",
    ]
    lines.extend(_bulletize(how_it_works))
    lines.extend(["", "## Examples", ""])
    lines.extend(_bulletize(examples))
    lines.extend(["", "## Use Cases", ""])
    lines.extend(_bulletize(use_cases))
    lines.extend(["", "## Failure Modes", ""])
    lines.extend(_bulletize(failure_modes))
    lines.extend(["", "## Related Concepts", ""])
    lines.extend(_bulletize([f"[[{item}]]" for item in links]))
    lines.extend(["", "## Claims and Provenance", ""])
    for claim_line in _clean_lines(candidate.body):
        lines.append(f"- Claim: {claim_line}")
        lines.append(f"  Source: {_source_lines(relative_path, candidate.source_notes)[0]}")
    if not _clean_lines(candidate.body):
        lines.append(f"- Claim: {candidate.summary.strip()}")
        lines.append(f"  Source: {_source_lines(relative_path, candidate.source_notes)[0]}")
    lines.extend(["", "## Sources", ""])
    for source_line in _source_lines(relative_path, candidate.source_notes):
        lines.append(f"- {source_line}")
    lines.append("")
    return "\n".join(lines)


def _render_flashcards_markdown(candidates: list[FlashcardCandidate], relative_path: str) -> str:
    title = candidates[0].title.strip()
    lines = [f"# Flashcards: {title}", "", "## Cards", ""]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(f"### {index}. {candidate.question.strip()}")
        lines.append("")
        lines.append(candidate.answer.strip())
        if candidate.related_pages:
            related = ", ".join(f"[[{item.strip()}]]" for item in candidate.related_pages if item.strip())
            if related:
                lines.extend(["", f"Related: {related}"])
        source_lines = _source_lines(relative_path, candidate.source_notes)
        lines.extend(["", f"Source: {source_lines[0]}", "", "---", ""])
    return "\n".join(lines).rstrip() + "\n"


def _expand_body_lines(body_lines: list[str]) -> list[str]:
    expanded: list[str] = []
    for index, line in enumerate(body_lines):
        expanded.append(line)
        if _needs_blank_line(line) and index < len(body_lines) - 1:
            expanded.append("")
    return expanded


def _needs_blank_line(line: str) -> bool:
    stripped = line.lstrip()
    return not (stripped.startswith("-") or stripped.startswith("|") or stripped.startswith("1."))


def _source_lines(relative_path: str, source_notes: list[str]) -> list[str]:
    base = f"`{relative_path}`"
    if not source_notes:
        return [base]
    return [f"{base}, {note.strip()}" for note in source_notes if note.strip()] or [base]


def _update_index_text(existing_text: str, entries: list[tuple[str, str, str]]) -> str:
    lines = existing_text.splitlines()
    by_type: dict[str, list[tuple[str, str]]] = {}
    for page_type, title, summary in entries:
        by_type.setdefault(page_type, []).append((title, summary))

    output = lines[:]
    for page_type, typed_entries in by_type.items():
        heading = INDEX_SECTION_BY_TYPE[page_type]
        try:
            heading_index = output.index(heading)
        except ValueError:
            output.extend(["", heading, ""])
            heading_index = output.index(heading)

        insertion_index = heading_index + 1
        while insertion_index < len(output) and not output[insertion_index].startswith("## "):
            insertion_index += 1

        existing_section = output[heading_index:insertion_index]
        additions = []
        for title, summary in typed_entries:
            entry = f"- [[{title}]] - {summary}"
            if entry not in existing_section:
                additions.append(entry)
        if additions:
            block = [""] + additions
            output[insertion_index:insertion_index] = block

    return "\n".join(output).rstrip() + "\n"


def _append_log_entry(existing_text: str, *, relative_path: str, generated_pages: list[str], flashcard_files: list[str]) -> str:
    timestamp = _now_iso()
    page_titles = ", ".join(Path(path).stem for path in generated_pages) or "none"
    flashcard_titles = ", ".join(Path(path).stem for path in flashcard_files) or "none"
    entry = (
        f"- {timestamp} | status: generated | source: `{relative_path}` | "
        f"pages: {page_titles} | flashcards: {flashcard_titles}"
    )
    normalized = existing_text.rstrip()
    return f"{normalized}\n{entry}\n"


def _insert_wiki_page_row(
    conn: sqlite3.Connection,
    *,
    extraction_id: str,
    page_type: str,
    target_path: Path,
    relative_path: str,
    markdown: str,
) -> None:
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO wiki_pages(id, extraction_id, page_type, path, relative_path, sha256, created_at, updated_at, status)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            extraction_id,
            page_type,
            str(target_path),
            relative_path,
            hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
            now,
            now,
            "created",
        ),
    )


def _record_audit_event(
    *,
    vault_path: Path,
    event_type: str,
    target_path: str | None,
    source_paths: list[str],
    summary: str,
    details: dict[str, object],
    conn: sqlite3.Connection | None = None,
) -> None:
    payload = {
        "id": str(uuid.uuid4()),
        "event_type": event_type,
        "target_path": target_path,
        "source_paths_json": json.dumps(source_paths),
        "summary": summary,
        "details_json": json.dumps(details),
        "created_at": _now_iso(),
    }

    def write_event(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            INSERT INTO audit_events(id, event_type, target_path, source_paths_json, summary, details_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["id"],
                payload["event_type"],
                payload["target_path"],
                payload["source_paths_json"],
                payload["summary"],
                payload["details_json"],
                payload["created_at"],
            ),
        )

    if conn is not None:
        write_event(conn)
    else:
        with connect_database(vault_path) as connection:
            write_event(connection)
            connection.commit()

    audit_path = vault_path / ".llm-wiki" / "audit.jsonl"
    _append_text(vault_path, audit_path, json.dumps(payload, ensure_ascii=True) + "\n")


def _append_text(vault_path: Path, path: Path, content: str) -> None:
    _assert_allowed_write(vault_path, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)


def _atomic_write_text(vault_path: Path, path: Path, content: str) -> None:
    _assert_allowed_write(vault_path, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(content.rstrip() + "\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _assert_allowed_write(vault_path: Path, path: Path) -> None:
    resolved = path.resolve()
    for root in ALLOWED_WRITE_ROOTS:
        allowed_root = (vault_path / root).resolve()
        if resolved.is_relative_to(allowed_root):
            return
    raise ValueError(f"Unsafe write target: {path}")


def _candidate_titles(payload: CandidatePayload) -> dict[str, list[str]]:
    return {
        "concepts": [item.title.strip() for item in payload.concepts],
        "entities": [item.title.strip() for item in payload.entities],
        "comparisons": [item.title.strip() for item in payload.comparisons],
        "maps": [item.title.strip() for item in payload.maps],
        "flashcards": [item.title.strip() for item in payload.flashcards],
    }


def _payload_candidate_count(payload: CandidatePayload) -> int:
    return (
        len(payload.concepts)
        + len(payload.entities)
        + len(payload.comparisons)
        + len(payload.maps)
        + len(payload.flashcards)
    )


def _sanitize_filename(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    safe = re.sub(r'[<>:"/\\|?*]', "", collapsed)
    safe = safe.rstrip(" .")
    return safe


def _canonical_wiki_title(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    no_separators = collapsed.replace("/", " ").replace("\\", " ")
    normalized = re.sub(r"\s+", " ", no_separators).strip()
    return normalized


def _should_create_page(*, page_type: str, candidate: PageCandidate) -> bool:
    summary_len = len(candidate.summary.strip())
    body_count = len(_clean_lines(candidate.body))
    link_count = len([link for link in candidate.links if _canonical_wiki_title(link)])
    if summary_len < 40:
        return False
    if page_type == "concept" and body_count < 2 and len(_clean_lines(candidate.examples)) == 0:
        return False
    if page_type == "concept" and link_count == 0:
        return False
    return True


def _clean_lines(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item and item.strip()]


def _extract_examples(body: list[str]) -> list[str]:
    examples = []
    for line in _clean_lines(body):
        lowered = line.lower()
        if "example" in lowered or "`" in line or ":" in line:
            examples.append(line)
    return examples


def _bulletize(items: list[str]) -> list[str]:
    cleaned = _clean_lines(items)
    if not cleaned:
        return ["- Not enough source evidence yet."]
    return [f"- {item}" for item in cleaned]


def _vault_id(vault_path: Path) -> str:
    return hashlib.sha256(str(vault_path.resolve()).encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
