from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_backend.core.config import load_config
from llm_wiki_backend.core.errors import LLMOutputError, WikiGenerationError
from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.llm.groq import GroqLLMProvider
from llm_wiki_backend.llm.provider import LLMProvider
from llm_wiki_backend.security.secrets import load_groq_key
from llm_wiki_backend.wiki.markdown import (
    PAGE_DIRECTORIES,
    append_log,
    atomic_write_text,
    extract_summary,
    extract_title,
    render_flashcards,
    render_page,
    safe_markdown_filename,
    sha256_text,
    title_exists_anywhere,
    update_index,
)
from llm_wiki_backend.wiki.models import (
    WikiCandidatePreview,
    WikiGenerationSummary,
    WikiSourceResult,
    coverage_decision_schema,
    generation_plan_schema,
    parse_coverage_decision,
    parse_generation_plan,
)
from llm_wiki_backend.wiki.review_service import (
    create_update_proposals,
    find_related_pages,
    find_title_matches,
    index_wiki_page,
)

PROMPT_PATH = Path(__file__).resolve().parents[5] / "packages" / "shared" / "prompts" / "wiki_generation.md"
COVERAGE_PROMPT_PATH = Path(__file__).resolve().parents[5] / "packages" / "shared" / "prompts" / "wiki_coverage_check.md"


def generate_wiki_for_pending_sources(vault_path: Path, provider: LLMProvider | None = None) -> WikiGenerationSummary:
    active_provider = provider or get_wiki_llm_provider(vault_path)
    if active_provider is None:
        return WikiGenerationSummary(skipped_reason="Groq is not configured.")

    ingest_run_id = str(uuid.uuid4())
    with connect_database(vault_path) as conn:
        rows = conn.execute(
            """
            SELECT
              files.id AS file_id,
              files.relative_path,
              files.sha256,
              extractions.id AS extraction_id,
              extractions.title,
              extractions.extracted_text
            FROM files
            JOIN extractions ON extractions.file_id = files.id
            WHERE files.vault_id = ?
              AND files.processing_status IN ('processed', 'extraction_limited')
              AND (files.wiki_generated_sha256 IS NULL OR files.wiki_generated_sha256 != files.sha256)
            ORDER BY files.relative_path ASC
            """,
            (_vault_id(vault_path),),
        ).fetchall()

        summary = WikiGenerationSummary(attempted_source_count=len(rows), ingest_run_id=ingest_run_id)
        for row in rows:
            result = _generate_for_source(
                conn=conn,
                vault_path=vault_path,
                provider=active_provider,
                ingest_run_id=ingest_run_id,
                file_id=row["file_id"],
                extraction_id=row["extraction_id"],
                source_relative_path=row["relative_path"],
                source_sha256=row["sha256"],
                source_title=row["title"],
                extracted_text=row["extracted_text"] or "",
            )
            summary.source_results.append(result)
            if result.status == "failed":
                summary.failed_count += 1
                continue
            summary.processed_source_count += 1
            summary.generated_page_count += len(result.generated_page_paths)
            summary.proposed_update_count += len(result.proposed_updates)
            if result.flashcard_path:
                summary.generated_flashcard_count += 1

        conn.commit()
    return summary


def get_wiki_llm_provider(vault_path: Path) -> LLMProvider | None:
    config = load_config(vault_path)
    api_key = load_groq_key(vault_path)
    if config is None or api_key is None:
        return None
    return GroqLLMProvider(api_key=api_key, model=config.provider.default_text_model)


def _generate_for_source(
    *,
    conn,
    vault_path: Path,
    provider: LLMProvider,
    ingest_run_id: str,
    file_id: str,
    extraction_id: str,
    source_relative_path: str,
    source_sha256: str,
    source_title: str | None,
    extracted_text: str,
) -> WikiSourceResult:
    if not extracted_text.strip():
        return _mark_generated(
            conn,
            file_id=file_id,
            source_sha256=source_sha256,
            result=WikiSourceResult(source_path=source_relative_path, status="skipped", error_message="No extracted text."),
        )

    try:
        title_candidates = find_title_matches(conn, source_title=source_title, limit=5)
        fts_candidates = find_related_pages(conn, source_title=source_title, extracted_text=extracted_text, limit=5)
        merged_by_path: dict[str, dict[str, object]] = {}
        for item in title_candidates + fts_candidates:
            key = str(item.get("target_path") or "")
            if not key:
                continue
            existing = merged_by_path.get(key)
            if existing is None:
                merged_by_path[key] = dict(item)
                continue
            existing_kind = str(existing.get("match_kind") or "")
            incoming_kind = str(item.get("match_kind") or "")
            if existing_kind != "title_exact" and incoming_kind == "title_exact":
                merged_by_path[key] = dict(item)
        related_candidates = _rank_related_candidates(list(merged_by_path.values()))

        if related_candidates:
            index_markdown = _try_read_index_markdown(vault_path)
            coverage_payload = provider.complete_structured(
                system_prompt=_load_coverage_prompt(),
                user_prompt=json.dumps(
                    {
                        "source_path": source_relative_path,
                        "source_title": source_title or Path(source_relative_path).stem,
                        "extracted_text": extracted_text,
                        "wiki_index_markdown": index_markdown,
                        "candidate_pages": [
                            {
                                "target_title": item["target_title"],
                                "target_path": item["target_path"],
                                "summary": item.get("summary") or "",
                                "selection_reason": item.get("selection_reason") or "",
                                "rank": index + 1,
                            }
                            for index, item in enumerate(related_candidates[:5])
                        ],
                    },
                    ensure_ascii=False,
                ),
                schema=coverage_decision_schema(),
            )
            decision = parse_coverage_decision(coverage_payload)
            if decision.verdict in {"covered", "unsure"}:
                selected_paths = {page.target_path for page in decision.selected_pages}
                if not selected_paths:
                    selected_paths = {str(related_candidates[0]["target_path"])}
                proposal_candidates = [c for c in related_candidates if str(c["target_path"]) in selected_paths]
                proposed_updates = create_update_proposals(
                    conn,
                    vault_path=vault_path,
                    provider=provider,
                    source_file_id=file_id,
                    source_relative_path=source_relative_path,
                    source_sha256=source_sha256,
                    source_title=source_title,
                    extracted_text=extracted_text,
                    candidates=proposal_candidates,
                    ingest_run_id=ingest_run_id,
                    model=getattr(provider, "_model", getattr(provider, "model", "review")),
                )
                status = "generated" if proposed_updates else "skipped"
                return _mark_generated(
                    conn,
                    file_id=file_id,
                    source_sha256=source_sha256,
                    result=WikiSourceResult(
                        source_path=source_relative_path,
                        status=status,
                        candidates=[],
                        proposed_updates=proposed_updates,
                        generated_page_paths=[],
                        skipped_titles=[],
                        flashcard_path=None,
                        index_updated=False,
                        log_updated=False,
                    ),
                )

        payload = provider.complete_structured(
            system_prompt=_load_prompt(),
            user_prompt=_build_user_prompt(source_relative_path, source_title, extracted_text),
            schema=generation_plan_schema(),
        )
        plan = parse_generation_plan(payload)
        result = _write_generation_plan(
            conn=conn,
            vault_path=vault_path,
            extraction_id=extraction_id,
            source_relative_path=source_relative_path,
            source_sha256=source_sha256,
            source_file_id=file_id,
            source_title=source_title,
            plan=plan,
            provider=provider,
            related_candidates=related_candidates,
            ingest_run_id=ingest_run_id,
        )
        return _mark_generated(conn, file_id=file_id, source_sha256=source_sha256, result=result)
    except (LLMOutputError, WikiGenerationError, OSError, ValueError) as exc:
        return WikiSourceResult(
            source_path=source_relative_path,
            status="failed",
            error_message=str(exc),
        )


def _write_generation_plan(
    conn,
    vault_path: Path,
    extraction_id: str,
    source_relative_path: str,
    source_sha256: str,
    source_file_id: str,
    source_title: str | None,
    plan,
    provider: LLMProvider,
    related_candidates: list[dict[str, object]],
    ingest_run_id: str,
) -> WikiSourceResult:
    previews: list[WikiCandidatePreview] = []
    generated_paths: list[str] = []
    skipped_titles: list[str] = []
    index_entries: list[tuple[str, str, str]] = []
    seen_target_paths: set[str] = set()

    for candidate in plan.candidates:
        rel_path = (PAGE_DIRECTORIES[candidate.page_type] / safe_markdown_filename(candidate.title)).as_posix()
        previews.append(
            WikiCandidatePreview(
                page_type=candidate.page_type,
                title=candidate.title,
                summary=candidate.summary,
                target_path=rel_path,
            )
        )
        if rel_path in seen_target_paths or title_exists_anywhere(vault_path, candidate.title):
            skipped_titles.append(candidate.title)
            continue
        seen_target_paths.add(rel_path)
        target_path = vault_path / rel_path
        content = render_page(candidate, source_relative_path)
        atomic_write_text(target_path, content)
        generated_paths.append(rel_path)
        index_entries.append((candidate.page_type, candidate.title, candidate.summary))
        conn.execute(
            """
            INSERT INTO wiki_pages(id, extraction_id, page_type, path, relative_path, sha256, title, summary, created_at, updated_at, status)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                extraction_id,
                candidate.page_type,
                str(target_path),
                rel_path,
                sha256_text(content),
                candidate.title,
                candidate.summary,
                _now_iso(),
                _now_iso(),
                "generated",
            ),
        )
        page_row = conn.execute(
            "SELECT id FROM wiki_pages WHERE relative_path = ? ORDER BY created_at DESC LIMIT 1",
            (rel_path,),
        ).fetchone()
        if page_row is not None:
            index_wiki_page(
                conn,
                wiki_page_id=page_row["id"],
                relative_path=rel_path,
                title=candidate.title,
                summary=candidate.summary,
                content=content,
            )

    flashcard_path = None
    if plan.flashcards:
        title = source_title or Path(source_relative_path).stem
        rel_path = Path("Wiki/Flashcards") / safe_markdown_filename(title)
        if not (vault_path / rel_path).exists():
            flashcard_content = render_flashcards(title, plan.flashcards, source_relative_path)
            atomic_write_text(vault_path / rel_path, flashcard_content)
            flashcard_path = rel_path.as_posix()
            for card in plan.flashcards:
                conn.execute(
                    """
                    INSERT INTO flashcards(id, extraction_id, question, answer, created_at)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), extraction_id, card.question, card.answer, _now_iso()),
                )

    index_updated = update_index(vault_path / "Wiki" / "index.md", index_entries)
    log_updated = append_log(
        vault_path / "Wiki" / "log.md",
        source_relative_path=source_relative_path,
        generated_pages=generated_paths + ([flashcard_path] if flashcard_path else []),
        status="generated" if generated_paths or flashcard_path else "skipped",
    )
    status = "generated" if generated_paths or flashcard_path else "skipped"
    proposed_updates = create_update_proposals(
        conn,
        vault_path=vault_path,
        provider=provider,
        source_file_id=source_file_id,
        source_relative_path=source_relative_path,
        source_sha256=source_sha256,
        source_title=source_title,
        extracted_text=conn.execute(
            "SELECT extracted_text FROM extractions WHERE id = ?",
            (extraction_id,),
        ).fetchone()["extracted_text"]
        or "",
        candidates=related_candidates,
        ingest_run_id=ingest_run_id,
        model=getattr(provider, "_model", getattr(provider, "model", "review")),
    )
    if proposed_updates and status == "skipped":
        status = "generated"
    return WikiSourceResult(
        source_path=source_relative_path,
        status=status,
        candidates=previews,
        proposed_updates=proposed_updates,
        generated_page_paths=generated_paths,
        skipped_titles=skipped_titles,
        flashcard_path=flashcard_path,
        index_updated=index_updated,
        log_updated=log_updated,
    )


def _mark_generated(conn, *, file_id: str, source_sha256: str, result: WikiSourceResult) -> WikiSourceResult:
    conn.execute(
        "UPDATE files SET wiki_generated_sha256 = ?, wiki_generated_at = ? WHERE id = ?",
        (source_sha256, _now_iso(), file_id),
    )
    return result


def _vault_id(vault_path: Path) -> str:
    import hashlib

    return hashlib.sha256(str(vault_path.resolve()).encode("utf-8")).hexdigest()


def _build_user_prompt(source_relative_path: str, source_title: str | None, extracted_text: str) -> str:
    title_line = source_title or Path(source_relative_path).stem
    return json.dumps(
        {
            "source_path": source_relative_path,
            "source_title": title_line,
            "extracted_text": extracted_text,
        },
        ensure_ascii=False,
    )


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_coverage_prompt() -> str:
    return COVERAGE_PROMPT_PATH.read_text(encoding="utf-8")


def _try_read_index_markdown(vault_path: Path) -> str:
    index_path = vault_path / "Wiki" / "index.md"
    try:
        if index_path.exists() and index_path.is_file():
            return index_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""


def _rank_related_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    def sort_key(item: dict[str, object]) -> tuple[int, float]:
        kind = str(item.get("match_kind") or "")
        priority = 0 if kind == "title_exact" else 1
        score = float(item.get("score") or 0.0)
        return (priority, score)

    return sorted(candidates, key=sort_key)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
