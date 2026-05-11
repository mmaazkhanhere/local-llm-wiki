from __future__ import annotations

import uuid
import json
import re
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_backend.db.service import connect_database
from llm_wiki_backend.lint.models import LintRunSummary, LintStatus, SemanticLintResult
from llm_wiki_backend.llm.provider import LLMProvider
from llm_wiki_backend.wiki.service import get_wiki_llm_provider
from llm_wiki_backend.observability.logging import get_logger
from llm_wiki_backend.observability.audit import record_audit_event
from llm_wiki_backend.wiki.markdown import atomic_write_text, extract_summary, extract_title, update_index
from llm_wiki_backend.wiki.review_service import build_diff_lines

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


_WIKILINK_RE = re.compile(r"\[\[([^\]\n|]+)(?:\|[^\]\n]+)?\]\]")
_SOURCE_RE = re.compile(r"^\s*-?\s*Source:\s*`([^`]+)`", re.IGNORECASE | re.MULTILINE)


def _normalize_slug(value: str) -> str:
    slug = re.sub(r"\s+", " ", value).strip().lower()
    slug = re.sub(r"[^a-z0-9 _-]+", "", slug)
    return slug


def _fingerprint(*parts: str) -> str:
    payload = "||".join(part.strip() for part in parts if part is not None)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iter_wiki_pages(vault_path: Path) -> list[Path]:
    wiki_root = vault_path / "Wiki"
    if not wiki_root.exists():
        return []
    return [p for p in wiki_root.rglob("*.md") if p.is_file()]


def _read_text_best_effort(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _index_link_targets(index_markdown: str) -> set[str]:
    return {_normalize_slug(match.group(1)) for match in _WIKILINK_RE.finditer(index_markdown or "")}


def _lint_mechanical(vault_path: Path) -> list[dict[str, object]]:
    """
    Deterministic lint checks (Phase 6.2).
    Returns a list of issue dicts ready for persistence.
    """
    pages = _iter_wiki_pages(vault_path)
    if not pages:
        return []

    index_path = vault_path / "Wiki" / "index.md"
    index_markdown = _read_text_best_effort(index_path) if index_path.exists() else ""
    index_targets = _index_link_targets(index_markdown)

    stem_to_paths: dict[str, list[str]] = {}
    rel_to_content: dict[str, str] = {}

    for path in pages:
        rel = path.relative_to(vault_path).as_posix()
        content = _read_text_best_effort(path)
        rel_to_content[rel] = content
        stem = _normalize_slug(path.stem)
        stem_to_paths.setdefault(stem, []).append(rel)

    known_slugs = set(stem_to_paths.keys())
    issues: list[dict[str, object]] = []

    # Duplicate slugs across wiki pages.
    for stem, rels in stem_to_paths.items():
        if len(rels) <= 1:
            continue
        issues.append(
            {
                "severity": "error",
                "issue_type": "duplicate_slug",
                "page_relative_path": None,
                "fingerprint": _fingerprint("duplicate_slug", stem),
                "details": {"slug": stem, "paths": sorted(rels)},
            }
        )

    # Empty pages (excluding index/log which can exist but should not be empty in practice).
    for rel, content in rel_to_content.items():
        if rel in {"Wiki/index.md", "Wiki/log.md"}:
            continue
        if content.strip():
            continue
        issues.append(
            {
                "severity": "error",
                "issue_type": "empty_page",
                "page_relative_path": rel,
                "fingerprint": _fingerprint("empty_page", rel),
                "details": {},
            }
        )

    # Broken internal links based on slug resolution within Wiki/.
    for rel, content in rel_to_content.items():
        for match in _WIKILINK_RE.finditer(content or ""):
            target = match.group(1)
            target_slug = _normalize_slug(target)
            if not target_slug:
                continue
            if target_slug in known_slugs:
                continue
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "broken_internal_link",
                    "page_relative_path": rel,
                    "fingerprint": _fingerprint("broken_internal_link", rel, target_slug),
                    "details": {"target": target},
                }
            )

    # Broken source references: Source lines must point to an existing Raw/ file.
    raw_root = (vault_path / "Raw").resolve()
    for rel, content in rel_to_content.items():
        for match in _SOURCE_RE.finditer(content or ""):
            raw_ref = match.group(1).strip()
            if not raw_ref:
                continue
            candidate = (vault_path / raw_ref).resolve()
            if raw_root not in candidate.parents and candidate != raw_root:
                issues.append(
                    {
                        "severity": "error",
                        "issue_type": "broken_source_reference",
                        "page_relative_path": rel,
                        "fingerprint": _fingerprint("broken_source_reference", rel, raw_ref),
                        "details": {"source": raw_ref, "reason": "Source path is not under Raw/"},
                    }
                )
                continue
            if not candidate.exists() or not candidate.is_file():
                issues.append(
                    {
                        "severity": "error",
                        "issue_type": "broken_source_reference",
                        "page_relative_path": rel,
                        "fingerprint": _fingerprint("broken_source_reference", rel, raw_ref),
                        "details": {"source": raw_ref, "reason": "Source file does not exist"},
                    }
                )

    # Invalid frontmatter fences (--- ... ---) at top-of-file.
    for rel, content in rel_to_content.items():
        lines = (content or "").splitlines()
        if not lines:
            continue
        if lines[0].strip() != "---":
            continue
        # Find closing fence in the next 100 lines.
        closing = None
        for idx, line in enumerate(lines[1:101], start=2):
            if line.strip() == "---":
                closing = idx
                break
        if closing is None:
            issues.append(
                {
                    "severity": "error",
                    "issue_type": "invalid_frontmatter",
                    "page_relative_path": rel,
                    "fingerprint": _fingerprint("invalid_frontmatter", rel),
                    "details": {"reason": "Missing closing frontmatter fence"},
                }
            )

    # Missing index entries for canonical page types.
    for rel in rel_to_content.keys():
        if not (rel.startswith("Wiki/Concepts/") or rel.startswith("Wiki/Entities/") or rel.startswith("Wiki/Comparisons/") or rel.startswith("Wiki/Maps/")):
            continue
        slug = _normalize_slug(Path(rel).stem)
        if not slug:
            continue
        if slug in index_targets:
            continue
        issues.append(
            {
                "severity": "warning",
                "issue_type": "missing_index_entry",
                "page_relative_path": rel,
                "fingerprint": _fingerprint("missing_index_entry", rel),
                "details": {},
            }
        )

    # Missing log file is a mechanical issue.
    log_path = vault_path / "Wiki" / "log.md"
    if not log_path.exists():
        issues.append(
            {
                "severity": "warning",
                "issue_type": "missing_log_file",
                "page_relative_path": "Wiki/log.md",
                "fingerprint": _fingerprint("missing_log_file"),
                "details": {},
            }
        )
    else:
        log_text = _read_text_best_effort(log_path)
        if len(log_text.strip().splitlines()) <= 1:
            issues.append(
                {
                    "severity": "warning",
                    "issue_type": "missing_log_entries",
                    "page_relative_path": "Wiki/log.md",
                    "fingerprint": _fingerprint("missing_log_entries"),
                    "details": {},
                }
            )

    return issues


def _lint_provenance(vault_path: Path) -> list[dict[str, object]]:
    """
    Provenance/citation lint (Phase 6.3).
    This is still deterministic: it verifies that pages have at least one Raw-backed Source reference.
    """
    pages = _iter_wiki_pages(vault_path)
    if not pages:
        return []

    raw_root = (vault_path / "Raw").resolve()
    issues: list[dict[str, object]] = []

    for path in pages:
        rel = path.relative_to(vault_path).as_posix()
        if rel in {"Wiki/index.md", "Wiki/log.md"}:
            continue
        if rel.startswith("Wiki/Reviews/") or rel.startswith("Wiki/Flashcards/"):
            continue
        if not (
            rel.startswith("Wiki/Concepts/")
            or rel.startswith("Wiki/Entities/")
            or rel.startswith("Wiki/Comparisons/")
            or rel.startswith("Wiki/Maps/")
        ):
            continue

        content = _read_text_best_effort(path)
        sources = [m.group(1).strip() for m in _SOURCE_RE.finditer(content or "")]
        if not sources:
            issues.append(
                {
                    "severity": "warning",
                    "issue_type": "missing_source_reference",
                    "page_relative_path": rel,
                    "fingerprint": _fingerprint("missing_source_reference", rel),
                    "details": {},
                }
            )
            continue

        # Ensure at least one source is Raw-backed.
        has_raw = False
        for src in sources:
            candidate = (vault_path / src).resolve()
            if raw_root in candidate.parents or candidate == raw_root:
                has_raw = True
                break
        if not has_raw:
            issues.append(
                {
                    "severity": "warning",
                    "issue_type": "no_raw_backing_source",
                    "page_relative_path": rel,
                    "fingerprint": _fingerprint("no_raw_backing_source", rel),
                    "details": {"sources": sources},
                }
            )

    return issues


def _status_from_issues(issues: list[dict[str, object]]) -> LintStatus:
    severities = {str(item.get("severity") or "") for item in issues}
    if "error" in severities:
        return "mechanical_errors"
    # Semantic issues are stored as warnings/info but should bubble to needs_review.
    semantic_issue_types = {
        "contradiction",
        "stale_claim",
        "uncited_claim",
        "duplicate_concept",
        "missing_concept",
        "missing_crosslink",
        "overlong_page",
        "low_confidence_concept",
        "data_gap",
        "page_split_candidate",
    }
    if any(str(item.get("issue_type") or "") in semantic_issue_types for item in issues):
        return "needs_review"
    if "warning" in severities:
        return "warnings"
    return "clean"


def run_post_ingest_smoke_lint(*, vault_path: Path, ingest_run_id: str | None) -> LintRunSummary:
    """
    Phase 6.1: minimal post-ingest lint hook.

    This runner is intentionally conservative: it records a lint run and returns status, but does not
    rewrite wiki content. Deterministic checks and fixes are implemented in later phase 6 features.
    """
    started_at = _now_iso()
    lint_run_id = str(uuid.uuid4())

    issues = _lint_mechanical(vault_path) + _lint_provenance(vault_path)
    status: LintStatus = _status_from_issues(issues)
    mechanical_issue_count = sum(1 for item in issues if str(item.get("severity")) in {"error", "warning", "info"})
    semantic_issue_count = 0
    fixes_applied_count = 0
    review_pages_created_count = 0
    error_message: str | None = None

    try:
        with connect_database(vault_path) as conn:
            created_at = _now_iso()
            for item in issues:
                conn.execute(
                    """
                    INSERT INTO lint_issues(
                      id, lint_run_id, severity, issue_type, page_relative_path,
                      status, fingerprint, details_json, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        lint_run_id,
                        str(item["severity"]),
                        str(item["issue_type"]),
                        item.get("page_relative_path"),
                        "open",
                        str(item["fingerprint"]),
                        json.dumps(item.get("details") or {}, ensure_ascii=False),
                        created_at,
                    ),
                )
            conn.execute(
                """
                INSERT INTO lint_runs(
                  id, ingest_run_id, status,
                  mechanical_issue_count, semantic_issue_count,
                  fixes_applied_count, review_pages_created_count,
                  started_at, finished_at, error_message
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lint_run_id,
                    ingest_run_id,
                    status,
                    mechanical_issue_count,
                    semantic_issue_count,
                    fixes_applied_count,
                    review_pages_created_count,
                    started_at,
                    _now_iso(),
                    error_message,
                ),
            )
            conn.commit()

        _append_lint_log_entry(
            vault_path=vault_path,
            ingest_run_id=ingest_run_id,
            status=status,
            mechanical_issue_count=mechanical_issue_count,
            semantic_issue_count=semantic_issue_count,
            fixes_applied_count=fixes_applied_count,
            review_pages_created_count=review_pages_created_count,
        )
    except Exception as exc:  # noqa: BLE001 - lint must not break ingest.
        logger.exception("Post-ingest lint failed: %s", exc)
        status = "lint_failed"
        error_message = str(exc)
        # Best-effort: try to persist failure.
        try:
            with connect_database(vault_path) as conn:
                conn.execute(
                    """
                    INSERT INTO lint_runs(
                      id, ingest_run_id, status,
                      mechanical_issue_count, semantic_issue_count,
                      fixes_applied_count, review_pages_created_count,
                      started_at, finished_at, error_message
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lint_run_id,
                        ingest_run_id,
                        status,
                        mechanical_issue_count,
                        semantic_issue_count,
                        fixes_applied_count,
                        review_pages_created_count,
                        started_at,
                        _now_iso(),
                        error_message,
                    ),
                )
                conn.commit()
        except Exception:  # noqa: BLE001
            pass

    return LintRunSummary(
        lint_run_id=lint_run_id,
        ingest_run_id=ingest_run_id,
        status=status,
        mechanical_issue_count=mechanical_issue_count,
        semantic_issue_count=semantic_issue_count,
        fixes_applied_count=fixes_applied_count,
        review_pages_created_count=review_pages_created_count,
        started_at=started_at,
        finished_at=_now_iso(),
        error_message=error_message,
    )


def run_semantic_lint(
    *,
    vault_path: Path,
    lint_run_id: str,
    provider: LLMProvider | None = None,
    max_pages: int = 6,
) -> int:
    """
    Phase 6.5: semantic lint that creates issues only (no edits).
    Returns the number of semantic issues recorded.
    """
    active_provider = provider or get_wiki_llm_provider(vault_path)
    if active_provider is None:
        return 0

    prompt_path = Path(__file__).resolve().parents[5] / "packages" / "shared" / "prompts" / "lint_semantic.md"
    system_prompt = prompt_path.read_text(encoding="utf-8")

    with connect_database(vault_path) as conn:
        rows = conn.execute(
            """
            SELECT relative_path
            FROM wiki_pages
            WHERE relative_path LIKE 'Wiki/%'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (max_pages,),
        ).fetchall()

        page_rels = [str(r["relative_path"]) for r in rows]
        pages: list[dict[str, str]] = []
        for rel in page_rels:
            path = vault_path / rel
            if not path.exists():
                continue
            pages.append({"path": rel, "content": _read_text_best_effort(path)[:8000]})

        if not pages:
            return 0

        payload = active_provider.complete_structured(
            system_prompt=system_prompt,
            user_prompt=json.dumps({"pages": pages}, ensure_ascii=False),
            schema=SemanticLintResult.model_json_schema(),
        )
        result = SemanticLintResult.model_validate(payload)

        created_at = _now_iso()
        count = 0
        for issue in result.issues:
            fingerprint = _fingerprint("semantic", issue.issue_type, ",".join(sorted(issue.affected_pages)), issue.summary)
            conn.execute(
                """
                INSERT INTO lint_issues(
                  id, lint_run_id, severity, issue_type, page_relative_path,
                  status, fingerprint, details_json, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    lint_run_id,
                    issue.severity,
                    issue.issue_type,
                    issue.affected_pages[0] if issue.affected_pages else None,
                    "open",
                    fingerprint,
                    json.dumps(issue.model_dump(), ensure_ascii=False),
                    created_at,
                ),
            )
            count += 1

        # Update lint run counters/status.
        existing = conn.execute(
            "SELECT status, semantic_issue_count FROM lint_runs WHERE id = ? LIMIT 1",
            (lint_run_id,),
        ).fetchone()
        if existing is not None:
            current_status = str(existing["status"])
            next_status = current_status
            if current_status != "mechanical_errors" and count > 0:
                next_status = "needs_review"
            conn.execute(
                "UPDATE lint_runs SET semantic_issue_count = semantic_issue_count + ?, status = ? WHERE id = ?",
                (count, next_status, lint_run_id),
            )

        conn.commit()
        if count > 0:
            _append_lint_log_entry(
                vault_path=vault_path,
                ingest_run_id=None,
                status="needs_review",
                mechanical_issue_count=0,
                semantic_issue_count=count,
                fixes_applied_count=0,
                review_pages_created_count=0,
            )
        return count


def create_semantic_review_pages(*, vault_path: Path, lint_run_id: str) -> list[dict[str, str]]:
    """
    Phase 6.6: materialize semantic lint issues as Review pages under Wiki/Reviews/.
    Uses issue fingerprints to avoid duplicates.
    """
    created: list[dict[str, str]] = []
    reviews_root = (vault_path / "Wiki" / "Reviews").resolve()
    reviews_root.mkdir(parents=True, exist_ok=True)

    semantic_issue_types = {
        "contradiction",
        "stale_claim",
        "uncited_claim",
        "duplicate_concept",
        "missing_concept",
        "missing_crosslink",
        "overlong_page",
        "low_confidence_concept",
        "data_gap",
        "page_split_candidate",
    }

    with connect_database(vault_path) as conn:
        rows = conn.execute(
            """
            SELECT fingerprint, issue_type, details_json
            FROM lint_issues
            WHERE lint_run_id = ?
            ORDER BY created_at ASC
            """,
            (lint_run_id,),
        ).fetchall()

        for row in rows:
            issue_type = str(row["issue_type"])
            if issue_type not in semantic_issue_types:
                continue
            fingerprint = str(row["fingerprint"])

            existing = conn.execute(
                "SELECT review_relative_path FROM review_pages WHERE issue_fingerprint = ? LIMIT 1",
                (fingerprint,),
            ).fetchone()
            if existing is not None:
                continue

            short = fingerprint[:8]
            review_rel = f"Wiki/Reviews/lint-{issue_type}-{short}.md"
            review_path = (vault_path / review_rel).resolve()
            if reviews_root not in review_path.parents:
                continue

            details = {}
            try:
                details = json.loads(row["details_json"] or "{}")
            except json.JSONDecodeError:
                details = {}

            affected = details.get("affected_pages") or []
            summary = details.get("summary") or ""
            evidence = details.get("evidence") or []

            lines = [f"# Review: {issue_type}", "", f"- Lint run: `{lint_run_id}`", f"- Fingerprint: `{short}`", ""]
            if summary:
                lines.extend(["## Summary", "", str(summary).strip(), ""])
            if affected:
                lines.extend(["## Affected Pages", ""])
                for item in affected:
                    lines.append(f"- `{item}`")
                lines.append("")
            if evidence:
                lines.extend(["## Evidence", ""])
                for item in evidence:
                    text = str(item).strip()
                    if not text:
                        continue
                    lines.append(f"- {text}")
                lines.append("")
            lines.extend(["## Suggested Next Step", "", "Review the affected pages and add/verify Raw sources as needed.", ""])

            atomic_write_text(review_path, "\n".join(lines).strip() + "\n")
            record_audit_event(
                conn,
                vault_path=vault_path,
                event_type="review_page_created",
                summary=f"Created semantic review page {review_rel}",
                target_file=review_rel,
                action="create_review_page",
                status="succeeded",
                extra_details={"lint_run_id": lint_run_id, "issue_fingerprint": fingerprint, "issue_type": issue_type},
            )
            conn.execute(
                """
                INSERT INTO review_pages(id, lint_run_id, issue_fingerprint, issue_type, review_relative_path, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    lint_run_id,
                    fingerprint,
                    issue_type,
                    review_rel,
                    _now_iso(),
                ),
            )
            created.append({"issue_type": issue_type, "review_relative_path": review_rel})

        if created:
            conn.execute(
                "UPDATE lint_runs SET review_pages_created_count = review_pages_created_count + ? WHERE id = ?",
                (len(created), lint_run_id),
            )
        conn.commit()

    if created:
        _append_lint_log_entry(
            vault_path=vault_path,
            ingest_run_id=None,
            status="needs_review",
            mechanical_issue_count=0,
            semantic_issue_count=0,
            fixes_applied_count=0,
            review_pages_created_count=len(created),
        )
    return created


def _append_lint_log_entry(
    *,
    vault_path: Path,
    ingest_run_id: str | None,
    status: str,
    mechanical_issue_count: int,
    semantic_issue_count: int,
    fixes_applied_count: int,
    review_pages_created_count: int,
) -> None:
    log_path = vault_path / "Wiki" / "log.md"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Processing Log\n"
    date_str = datetime.now(UTC).date().isoformat()
    header = f"## [{date_str}] lint | post-ingest smoke check"
    block = [
        header,
        "",
        f"- Ingest run: {ingest_run_id or '-'}",
        f"- Status: {status}",
        f"- Mechanical issues: {mechanical_issue_count}",
        f"- Semantic issues: {semantic_issue_count}",
        f"- Auto-fixes applied: {fixes_applied_count}",
        f"- Review pages created: {review_pages_created_count}",
        "",
    ]
    content = existing.rstrip() + "\n\n" + "\n".join(block)
    atomic_write_text(log_path, content.rstrip() + "\n")
    try:
        with connect_database(vault_path) as conn:
            record_audit_event(
                conn,
                vault_path=vault_path,
                event_type="lint_log_appended",
                summary="Appended lint entry to Wiki/log.md",
                ingest_run_id=ingest_run_id,
                target_file="Wiki/log.md",
                action="lint_log_append",
                status="succeeded",
                extra_details={
                    "lint_status": status,
                    "mechanical_issue_count": mechanical_issue_count,
                    "semantic_issue_count": semantic_issue_count,
                    "fixes_applied_count": fixes_applied_count,
                    "review_pages_created_count": review_pages_created_count,
                },
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


def latest_lint_status(*, vault_path: Path) -> LintRunSummary | None:
    with connect_database(vault_path) as conn:
        row = conn.execute(
            """
            SELECT
              id, ingest_run_id, status,
              mechanical_issue_count, semantic_issue_count,
              fixes_applied_count, review_pages_created_count,
              started_at, finished_at, error_message
            FROM lint_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return LintRunSummary(
            lint_run_id=row["id"],
            ingest_run_id=row["ingest_run_id"],
            status=row["status"],
            mechanical_issue_count=int(row["mechanical_issue_count"] or 0),
            semantic_issue_count=int(row["semantic_issue_count"] or 0),
            fixes_applied_count=int(row["fixes_applied_count"] or 0),
            review_pages_created_count=int(row["review_pages_created_count"] or 0),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error_message=row["error_message"],
        )


def apply_safe_fixes(*, vault_path: Path, lint_run_id: str, dry_run: bool = True) -> dict[str, object]:
    """
    Phase 6.4: apply safe mechanical fixes only.
    Currently supported:
    - missing_index_entry
    - missing_log_file
    - empty_page (mark as stub)
    """
    applied = 0
    planned = 0
    fixes: list[dict[str, object]] = []

    with connect_database(vault_path) as conn:
        issues = conn.execute(
            """
            SELECT fingerprint, issue_type, page_relative_path, details_json
            FROM lint_issues
            WHERE lint_run_id = ?
            ORDER BY created_at ASC
            """,
            (lint_run_id,),
        ).fetchall()

        for issue in issues:
            issue_type = str(issue["issue_type"])
            page_rel = issue["page_relative_path"]
            fingerprint = str(issue["fingerprint"])
            if issue_type == "missing_index_entry" and page_rel:
                target_path = vault_path / str(page_rel)
                if not target_path.exists():
                    continue
                content = target_path.read_text(encoding="utf-8")
                title = extract_title(content)
                summary = extract_summary(content)
                page_type = "concept"
                if str(page_rel).startswith("Wiki/Entities/"):
                    page_type = "entity"
                elif str(page_rel).startswith("Wiki/Comparisons/"):
                    page_type = "comparison"
                elif str(page_rel).startswith("Wiki/Maps/"):
                    page_type = "map"

                before = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8") if (vault_path / "Wiki" / "index.md").exists() else ""
                after = before
                planned += 1
                if not dry_run:
                    update_index(vault_path / "Wiki" / "index.md", [(page_type, title, summary)])
                    after = (vault_path / "Wiki" / "index.md").read_text(encoding="utf-8")
                    record_audit_event(
                        conn,
                        vault_path=vault_path,
                        event_type="lint_fix_applied",
                        summary=f"Added missing index entry for {page_rel}",
                        ingest_run_id=None,
                        target_file="Wiki/index.md",
                        action="add_index_entry",
                        status="succeeded",
                        extra_details={"lint_run_id": lint_run_id, "issue_fingerprint": fingerprint},
                    )
                    applied += 1
                diff = build_diff_lines(before, after)
                conn.execute(
                    """
                    INSERT INTO lint_fixes(
                      id, lint_run_id, issue_fingerprint, fix_type, target_relative_path,
                      dry_run, before_content, after_content, diff_json, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        lint_run_id,
                        fingerprint,
                        "add_index_entry",
                        "Wiki/index.md",
                        1 if dry_run else 0,
                        before,
                        after,
                        json.dumps(diff, ensure_ascii=False),
                        _now_iso(),
                    ),
                )
                fixes.append({"issue_type": issue_type, "fix_type": "add_index_entry", "target": "Wiki/index.md", "dry_run": dry_run})

            elif issue_type == "missing_log_file":
                log_rel = "Wiki/log.md"
                log_path = vault_path / log_rel
                before = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
                after = before or "# Processing Log\n"
                planned += 1
                if not dry_run:
                    atomic_write_text(log_path, after.rstrip() + "\n")
                    record_audit_event(
                        conn,
                        vault_path=vault_path,
                        event_type="lint_fix_applied",
                        summary="Created missing Wiki/log.md",
                        ingest_run_id=None,
                        target_file=log_rel,
                        action="create_log",
                        status="succeeded",
                        extra_details={"lint_run_id": lint_run_id, "issue_fingerprint": fingerprint},
                    )
                    applied += 1
                diff = build_diff_lines(before, after)
                conn.execute(
                    """
                    INSERT INTO lint_fixes(
                      id, lint_run_id, issue_fingerprint, fix_type, target_relative_path,
                      dry_run, before_content, after_content, diff_json, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        lint_run_id,
                        fingerprint,
                        "create_log",
                        log_rel,
                        1 if dry_run else 0,
                        before,
                        after,
                        json.dumps(diff, ensure_ascii=False),
                        _now_iso(),
                    ),
                )
                fixes.append({"issue_type": issue_type, "fix_type": "create_log", "target": log_rel, "dry_run": dry_run})

            elif issue_type == "empty_page" and page_rel:
                target_path = vault_path / str(page_rel)
                if not target_path.exists():
                    continue
                before = target_path.read_text(encoding="utf-8")
                title = Path(str(page_rel)).stem
                after = f"# {title}\n\n(Stub: page was empty during lint.)\n\n## Sources\n\n- Source: `Raw/...`, section \"...\"\n"
                planned += 1
                if not dry_run:
                    atomic_write_text(target_path, after)
                    record_audit_event(
                        conn,
                        vault_path=vault_path,
                        event_type="lint_fix_applied",
                        summary=f"Marked empty page as stub: {page_rel}",
                        ingest_run_id=None,
                        target_file=str(page_rel),
                        action="mark_stub",
                        status="succeeded",
                        extra_details={"lint_run_id": lint_run_id, "issue_fingerprint": fingerprint},
                    )
                    applied += 1
                diff = build_diff_lines(before, after)
                conn.execute(
                    """
                    INSERT INTO lint_fixes(
                      id, lint_run_id, issue_fingerprint, fix_type, target_relative_path,
                      dry_run, before_content, after_content, diff_json, created_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        lint_run_id,
                        fingerprint,
                        "mark_stub",
                        str(page_rel),
                        1 if dry_run else 0,
                        before,
                        after,
                        json.dumps(diff, ensure_ascii=False),
                        _now_iso(),
                    ),
                )
                fixes.append({"issue_type": issue_type, "fix_type": "mark_stub", "target": str(page_rel), "dry_run": dry_run})

        if not dry_run and applied:
            conn.execute(
                "UPDATE lint_runs SET fixes_applied_count = fixes_applied_count + ? WHERE id = ?",
                (applied, lint_run_id),
            )
        conn.commit()

    if not dry_run and applied:
        _append_lint_log_entry(
            vault_path=vault_path,
            ingest_run_id=None,
            status="warnings",
            mechanical_issue_count=0,
            semantic_issue_count=0,
            fixes_applied_count=applied,
            review_pages_created_count=0,
        )

    return {"planned": planned, "applied": applied, "fixes": fixes}
