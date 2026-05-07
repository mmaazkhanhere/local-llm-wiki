from __future__ import annotations

import difflib
import json
import re
import uuid
from pathlib import Path

from llm_wiki_backend.core.errors import WikiGenerationError
from llm_wiki_backend.observability.audit import now_iso, record_audit_event
from llm_wiki_backend.wiki.markdown import (
    append_log,
    atomic_write_text,
    extract_summary,
    extract_title,
    render_review_file,
    sha256_text,
    update_index,
)
from llm_wiki_backend.wiki.models import ProposedUpdatePreview, parse_update_plan, update_plan_schema

UPDATE_PROMPT_TEMPLATE = """You are reviewing whether an existing wiki page should be updated from a new source.
Return JSON only.
For each selected target, preserve editable markdown structure and citations.
Do not invent unrelated claims.
"""


def index_wiki_page(conn, *, wiki_page_id: str, relative_path: str, title: str, summary: str, content: str) -> None:
    conn.execute("DELETE FROM wiki_pages_fts WHERE wiki_page_id = ?", (wiki_page_id,))
    conn.execute(
        """
        INSERT INTO wiki_pages_fts(wiki_page_id, relative_path, title, summary, content)
        VALUES(?, ?, ?, ?, ?)
        """,
        (wiki_page_id, relative_path, title, summary, content),
    )


def find_related_pages(conn, *, source_title: str | None, extracted_text: str, limit: int = 5) -> list[dict[str, object]]:
    query = _fts_query(source_title, extracted_text)
    if not query:
        return []
    rows = conn.execute(
        """
        SELECT
          wiki_pages.id,
          wiki_pages.relative_path,
          wiki_pages.title,
          wiki_pages.summary,
          bm25(wiki_pages_fts, 2.0, 1.0, 0.4) AS score
        FROM wiki_pages_fts
        JOIN wiki_pages ON wiki_pages.id = wiki_pages_fts.wiki_page_id
        WHERE wiki_pages_fts MATCH ?
        ORDER BY score ASC
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    candidates: list[dict[str, object]] = []
    for row in rows:
        title = row["title"] or Path(row["relative_path"]).stem
        candidates.append(
            {
                "wiki_page_id": row["id"],
                "target_path": row["relative_path"],
                "target_title": title,
                "summary": row["summary"] or "",
                "score": float(row["score"]),
                "selection_reason": f"Matched wiki page terms against new source query `{query}`.",
            }
        )
    return candidates


def create_update_proposals(
    conn,
    *,
    vault_path: Path,
    provider,
    source_file_id: str,
    source_relative_path: str,
    source_sha256: str,
    source_title: str | None,
    extracted_text: str,
    candidates: list[dict[str, object]],
    ingest_run_id: str,
    model: str,
) -> list[ProposedUpdatePreview]:
    if not candidates:
        return []

    current_pages = []
    for candidate in candidates:
        target_path = vault_path / str(candidate["target_path"])
        if not target_path.exists():
            continue
        current_pages.append(
            {
                "target_title": candidate["target_title"],
                "target_path": candidate["target_path"],
                "current_content": target_path.read_text(encoding="utf-8"),
                "selection_reason": candidate["selection_reason"],
            }
        )

    if not current_pages:
        return []

    payload = provider.complete_structured(
        system_prompt=UPDATE_PROMPT_TEMPLATE,
        user_prompt=json.dumps(
            {
                "source_path": source_relative_path,
                "source_title": source_title or Path(source_relative_path).stem,
                "extracted_text": extracted_text,
                "candidate_pages": current_pages,
            },
            ensure_ascii=False,
        ),
        schema=update_plan_schema(),
    )
    plan = parse_update_plan(payload)
    previews: list[ProposedUpdatePreview] = []
    for item in plan.related_pages:
        matching = next((candidate for candidate in candidates if candidate["target_title"] == item.target_title), None)
        if matching is None:
            continue
        target_relative_path = str(matching["target_path"])
        target_path = vault_path / target_relative_path
        if not target_path.exists():
            continue
        old_content = target_path.read_text(encoding="utf-8")
        if item.proposed_content.strip() == old_content.strip():
            continue

        proposal_id = str(uuid.uuid4())
        review_relative_path = _review_path(item.target_title, proposal_id)
        review_content = render_review_file(
            target_title=item.target_title,
            target_relative_path=target_relative_path,
            source_relative_path=source_relative_path,
            reason=item.reason,
            current_content=old_content,
            proposed_content=item.proposed_content,
            citations=[citation.locator for citation in item.source_citations],
        )
        atomic_write_text(vault_path / review_relative_path, review_content)
        conn.execute(
            """
            INSERT INTO proposed_updates(
              id, wiki_page_id, source_file_id, source_relative_path, source_sha256, target_relative_path, target_title,
              old_content, proposed_content, reason, confidence, source_citations_json, review_path, ingest_run_id, model,
              target_sha256_at_creation, status, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                matching["wiki_page_id"],
                source_file_id,
                source_relative_path,
                source_sha256,
                target_relative_path,
                item.target_title,
                old_content,
                item.proposed_content,
                item.reason,
                item.confidence,
                json.dumps([citation.model_dump() for citation in item.source_citations], ensure_ascii=False),
                review_relative_path.as_posix(),
                ingest_run_id,
                model,
                sha256_text(old_content),
                "pending",
                now_iso(),
            ),
        )
        record_audit_event(
            conn,
            vault_path=vault_path,
            event_type="proposal_created",
            summary=f"Created review proposal for {target_relative_path}",
            proposal_id=proposal_id,
            ingest_run_id=ingest_run_id,
            source_file=source_relative_path,
            source_id=source_file_id,
            source_version=source_sha256,
            target_file=target_relative_path,
            action="proposal_created",
            model=model,
            old_hash=sha256_text(old_content),
            new_hash=sha256_text(item.proposed_content),
            status="pending",
            extra_details={
                "reason": item.reason,
                "confidence": item.confidence,
                "review_path": review_relative_path.as_posix(),
            },
        )
        previews.append(
            ProposedUpdatePreview(
                proposal_id=proposal_id,
                target_title=item.target_title,
                target_path=target_relative_path,
                reason=item.reason,
                confidence=item.confidence,
                source_citations=item.source_citations,
                review_path=review_relative_path.as_posix(),
                status="pending",
            )
        )
    return previews


def list_proposals(conn, *, status: str = "pending") -> list[dict[str, object]]:
    if status == "all":
        rows = conn.execute(
            """
            SELECT id, source_relative_path, target_relative_path, target_title, reason, confidence, proposed_content,
                   old_content, review_path, status, created_at, edited_at, resolved_at, last_error
            FROM proposed_updates
            ORDER BY created_at DESC
            """
        ).fetchall()
    elif status == "pending":
        rows = conn.execute(
            """
            SELECT id, source_relative_path, target_relative_path, target_title, reason, confidence, proposed_content,
                   old_content, review_path, status, created_at, edited_at, resolved_at, last_error
            FROM proposed_updates
            WHERE status IN ('pending', 'conflicted')
            ORDER BY created_at DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, source_relative_path, target_relative_path, target_title, reason, confidence, proposed_content,
                   old_content, review_path, status, created_at, edited_at, resolved_at, last_error
            FROM proposed_updates
            WHERE status = ?
            ORDER BY created_at DESC
            """,
            (status,),
        ).fetchall()
    return [_row_to_proposal_dict(row) for row in rows]


def get_proposal(conn, proposal_id: str) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT id, source_relative_path, target_relative_path, target_title, reason, confidence, proposed_content,
               old_content, review_path, status, created_at, edited_at, resolved_at, last_error, source_citations_json
        FROM proposed_updates
        WHERE id = ?
        """,
        (proposal_id,),
    ).fetchone()
    if row is None:
        return None
    payload = _row_to_proposal_dict(row)
    payload["source_citations"] = json.loads(row["source_citations_json"] or "[]")
    payload["diff"] = build_diff_lines(row["old_content"], row["proposed_content"])
    return payload


def edit_proposal(conn, *, vault_path: Path, proposal_id: str, proposed_content: str) -> dict[str, object]:
    row = _require_proposal(conn, proposal_id)
    review_content = render_review_file(
        target_title=row["target_title"],
        target_relative_path=row["target_relative_path"],
        source_relative_path=row["source_relative_path"],
        reason=row["reason"],
        current_content=row["old_content"],
        proposed_content=proposed_content,
        citations=[item.get("locator", "") for item in json.loads(row["source_citations_json"] or "[]") if item.get("locator")],
    )
    atomic_write_text(vault_path / row["review_path"], review_content)
    conn.execute(
        """
        UPDATE proposed_updates
        SET proposed_content = ?, status = ?, edited_at = ?, last_error = NULL
        WHERE id = ?
        """,
        (proposed_content, "pending", now_iso(), proposal_id),
    )
    return get_proposal(conn, proposal_id) or {}


def reject_proposal(conn, *, vault_path: Path, proposal_id: str) -> dict[str, object]:
    row = _require_proposal(conn, proposal_id)
    resolved_at = now_iso()
    conn.execute(
        "UPDATE proposed_updates SET status = 'rejected', resolved_at = ?, last_error = NULL WHERE id = ?",
        (resolved_at, proposal_id),
    )
    record_audit_event(
        conn,
        vault_path=vault_path,
        event_type="proposal_rejected",
        summary=f"Rejected review proposal for {row['target_relative_path']}",
        proposal_id=proposal_id,
        ingest_run_id=row["ingest_run_id"],
        source_file=row["source_relative_path"],
        source_id=row["source_file_id"],
        source_version=row["source_sha256"],
        target_file=row["target_relative_path"],
        action="rejected",
        model=row["model"],
        old_hash=row["target_sha256_at_creation"],
        new_hash=sha256_text(row["proposed_content"]),
        status="rejected",
    )
    return get_proposal(conn, proposal_id) or {}


def approve_proposal(conn, *, vault_path: Path, proposal_id: str) -> dict[str, object]:
    row = _require_proposal(conn, proposal_id)
    target_path = vault_path / row["target_relative_path"]
    current_content = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    current_hash = sha256_text(current_content)
    if current_hash != row["target_sha256_at_creation"]:
        message = (
            "Conflict: Target page was updated by another process after this proposal was generated. "
            "Approve again to regenerate and apply."
        )
        conn.execute(
            "UPDATE proposed_updates SET status = 'conflicted', last_error = ? WHERE id = ?",
            (message, proposal_id),
        )
        record_audit_event(
            conn,
            vault_path=vault_path,
            event_type="proposal_conflicted",
            summary=f"Conflict applying proposal for {row['target_relative_path']}",
            proposal_id=proposal_id,
            ingest_run_id=row["ingest_run_id"],
            source_file=row["source_relative_path"],
            source_id=row["source_file_id"],
            source_version=row["source_sha256"],
            target_file=row["target_relative_path"],
            action="conflict",
            model=row["model"],
            old_hash=row["target_sha256_at_creation"],
            new_hash=current_hash,
            status="conflicted",
        )
        return get_proposal(conn, proposal_id) or {}

    proposed_content = row["proposed_content"]
    atomic_write_text(target_path, proposed_content)
    new_hash = sha256_text(proposed_content)
    conn.execute(
        """
        UPDATE proposed_updates
        SET status = 'approved', resolved_at = ?, last_error = NULL
        WHERE id = ?
        """,
        (now_iso(), proposal_id),
    )
    conn.execute(
        """
        UPDATE wiki_pages
        SET sha256 = ?, updated_at = ?, title = ?, summary = ?, status = 'updated'
        WHERE id = ?
        """,
        (new_hash, now_iso(), extract_title(proposed_content), extract_summary(proposed_content), row["wiki_page_id"]),
    )
    index_wiki_page(
        conn,
        wiki_page_id=row["wiki_page_id"],
        relative_path=row["target_relative_path"],
        title=extract_title(proposed_content),
        summary=extract_summary(proposed_content),
        content=proposed_content,
    )
    record_audit_event(
        conn,
        vault_path=vault_path,
        event_type="proposal_approved",
        summary=f"Approved review proposal for {row['target_relative_path']}",
        proposal_id=proposal_id,
        ingest_run_id=row["ingest_run_id"],
        source_file=row["source_relative_path"],
        source_id=row["source_file_id"],
        source_version=row["source_sha256"],
        target_file=row["target_relative_path"],
        action="approved",
        model=row["model"],
        old_hash=row["target_sha256_at_creation"],
        new_hash=new_hash,
        status="approved",
    )
    record_audit_event(
        conn,
        vault_path=vault_path,
        event_type="target_file_written",
        summary=f"Wrote approved target file {row['target_relative_path']}",
        proposal_id=proposal_id,
        ingest_run_id=row["ingest_run_id"],
        source_file=row["source_relative_path"],
        source_id=row["source_file_id"],
        source_version=row["source_sha256"],
        target_file=row["target_relative_path"],
        action="target_file_written",
        model=row["model"],
        old_hash=row["target_sha256_at_creation"],
        new_hash=new_hash,
        status="succeeded",
    )
    _update_index_and_log_after_approval(conn, vault_path=vault_path, proposal_row=row, proposed_content=proposed_content)
    return get_proposal(conn, proposal_id) or {}


def approve_all_for_source(conn, *, vault_path: Path, source_relative_path: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT id
        FROM proposed_updates
        WHERE source_relative_path = ? AND status IN ('pending', 'conflicted')
        ORDER BY created_at ASC
        """,
        (source_relative_path,),
    ).fetchall()
    result = {"applied": 0, "conflicted": 0, "failed": 0}
    for row in rows:
        try:
            payload = approve_proposal(conn, vault_path=vault_path, proposal_id=row["id"])
            if payload.get("status") == "approved":
                result["applied"] += 1
            elif payload.get("status") == "conflicted":
                result["conflicted"] += 1
        except OSError:
            result["failed"] += 1
    return result


def build_diff_lines(old_content: str, new_content: str) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    for line in re.split(r"\r?\n", "\n".join(difflib.ndiff(old_content.splitlines(), new_content.splitlines()))):
        if not line:
            continue
        prefix = line[:2]
        content = line[2:]
        kind = "unchanged"
        if prefix == "+ ":
            kind = "added"
        elif prefix == "- ":
            kind = "removed"
        elif prefix == "? ":
            continue
        lines.append({"kind": kind, "text": content})
    return lines


def _review_path(target_title: str, proposal_id: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9 _-]+", "", target_title).strip() or "Review"
    slug = re.sub(r"\s+", " ", slug)
    return Path("Wiki/Reviews") / f"{slug} [{proposal_id[:8]}].md"


def _fts_query(source_title: str | None, extracted_text: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", f"{source_title or ''} {extracted_text}")
    stopwords = {"this", "that", "with", "from", "into", "have", "which", "about", "there", "their"}
    unique: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in stopwords or lowered in unique:
            continue
        unique.append(lowered)
    return " OR ".join(f'"{term}"' for term in unique[:8])


def _update_index_and_log_after_approval(conn, *, vault_path: Path, proposal_row, proposed_content: str) -> None:
    page_row = conn.execute(
        "SELECT page_type FROM wiki_pages WHERE id = ?",
        (proposal_row["wiki_page_id"],),
    ).fetchone()
    page_type = page_row["page_type"] if page_row else "concept"
    title = extract_title(proposed_content)
    summary = extract_summary(proposed_content)
    if update_index(vault_path / "Wiki" / "index.md", [(page_type, title, summary)]):
        record_audit_event(
            conn,
            vault_path=vault_path,
            event_type="index_updated",
            summary=f"Updated index for {proposal_row['target_relative_path']}",
            proposal_id=proposal_row["id"],
            ingest_run_id=proposal_row["ingest_run_id"],
            source_file=proposal_row["source_relative_path"],
            source_id=proposal_row["source_file_id"],
            source_version=proposal_row["source_sha256"],
            target_file="Wiki/index.md",
            action="index_updated",
            model=proposal_row["model"],
            status="succeeded",
        )
    if append_log(
        vault_path / "Wiki" / "log.md",
        source_relative_path=proposal_row["source_relative_path"],
        generated_pages=[proposal_row["target_relative_path"]],
        status="updated",
    ):
        record_audit_event(
            conn,
            vault_path=vault_path,
            event_type="log_updated",
            summary=f"Updated log for {proposal_row['target_relative_path']}",
            proposal_id=proposal_row["id"],
            ingest_run_id=proposal_row["ingest_run_id"],
            source_file=proposal_row["source_relative_path"],
            source_id=proposal_row["source_file_id"],
            source_version=proposal_row["source_sha256"],
            target_file="Wiki/log.md",
            action="log_updated",
            model=proposal_row["model"],
            status="succeeded",
        )


def _require_proposal(conn, proposal_id: str):
    row = conn.execute("SELECT * FROM proposed_updates WHERE id = ?", (proposal_id,)).fetchone()
    if row is None:
        raise WikiGenerationError(f"Unknown proposal id: {proposal_id}")
    return row


def _row_to_proposal_dict(row) -> dict[str, object]:
    return {
        "id": row["id"],
        "source_relative_path": row["source_relative_path"],
        "target_relative_path": row["target_relative_path"],
        "target_title": row["target_title"],
        "reason": row["reason"],
        "confidence": row["confidence"],
        "old_content": row["old_content"],
        "proposed_content": row["proposed_content"],
        "review_path": row["review_path"],
        "status": row["status"],
        "created_at": row["created_at"],
        "edited_at": row["edited_at"],
        "resolved_at": row["resolved_at"],
        "last_error": row["last_error"],
    }
