from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from llm_wiki_backend.core.config import load_config
from llm_wiki_backend.core.errors import LLMOutputError, WikiGenerationError
from llm_wiki_backend.llm.groq import GroqLLMProvider
from llm_wiki_backend.llm.provider import LLMProvider
from llm_wiki_backend.security.secrets import load_groq_key
from llm_wiki_backend.wiki.markdown import render_review_file, sha256_text


@dataclass
class AskCitationItem:
    citation_id: str
    kind: str
    path: str
    locator: str | None = None
    title: str | None = None
    content: str = ""


def get_ask_llm_provider(vault_path: Path) -> LLMProvider | None:
    config = load_config(vault_path)
    api_key = load_groq_key(vault_path)
    if config is None or api_key is None:
        return None
    return GroqLLMProvider(api_key=api_key, model=config.provider.default_text_model)


def ask_question(conn, *, vault_path: Path, question: str) -> dict:
    trimmed = question.strip()
    if not trimmed:
        raise WikiGenerationError("Question cannot be empty.")

    wiki_hits = search_wiki_pages(conn, query=trimmed, limit=4)
    neighbors = load_graph_neighbors(conn, vault_path=vault_path, wiki_hits=wiki_hits, limit=4)
    merged_wiki = dedupe_pages(wiki_hits + neighbors)

    used_raw = False
    raw_hits: list[AskCitationItem] = []
    if not merged_wiki:
        raw_hits = search_raw_chunks(conn, query=trimmed, limit=4)
        used_raw = len(raw_hits) > 0

    evidence = merged_wiki + raw_hits
    provider = get_ask_llm_provider(vault_path)
    if provider is None:
        return {
            "answer": "Unsupported: Ask requires a configured provider.",
            "unsupported": True,
            "citations": [],
            "trace": {
                "wiki_primary_count": len(wiki_hits),
                "neighbor_count": len(neighbors),
                "raw_used": used_raw,
                "raw_count": len(raw_hits),
            },
        }

    answer_payload = _generate_answer(provider=provider, question=trimmed, evidence=evidence)
    citation_map = {item.citation_id: item for item in evidence}
    citations: list[dict] = []
    for citation_id in answer_payload.get("citation_ids", []):
        item = citation_map.get(citation_id)
        if item is None:
            continue
        citations.append(
            {
                "citation_id": item.citation_id,
                "kind": item.kind,
                "path": item.path,
                "locator": item.locator,
                "title": item.title,
            }
        )

    return {
        "answer": answer_payload["answer"],
        "unsupported": bool(answer_payload.get("unsupported", False)),
        "citations": citations,
        "trace": {
            "wiki_primary_count": len(wiki_hits),
            "neighbor_count": len(neighbors),
            "raw_used": used_raw,
            "raw_count": len(raw_hits),
        },
    }


def create_proposed_update_from_answer(
    conn,
    *,
    vault_path: Path,
    question: str,
    answer: str,
    target_relative_path: str,
    target_title: str,
    reason: str,
    source_citations: list[dict],
) -> dict:
    target_path = (vault_path / target_relative_path).resolve()
    if not target_path.exists():
        raise WikiGenerationError("Target wiki page does not exist.")
    allowed_root = (vault_path / "Wiki").resolve()
    if allowed_root not in target_path.parents:
        raise WikiGenerationError("Target must be inside Wiki/.")

    old_content = target_path.read_text(encoding="utf-8")
    proposed_content = old_content.rstrip() + f"\n\n## Ask Update\n\nQ: {question.strip()}\n\n{answer.strip()}\n"
    if proposed_content.strip() == old_content.strip():
        raise WikiGenerationError("No change to propose.")

    page_row = conn.execute(
        "SELECT id FROM wiki_pages WHERE relative_path = ? ORDER BY updated_at DESC LIMIT 1",
        (target_relative_path,),
    ).fetchone()
    if page_row is None:
        raise WikiGenerationError("Target wiki page is not indexed.")

    proposal_id = str(uuid.uuid4())
    review_relative_path = Path("Wiki/Reviews") / f"Ask update {target_title} {proposal_id[:8]}.md"
    citations = [item.get("locator", "") for item in source_citations if item.get("locator")]
    review_content = render_review_file(
        target_title=target_title,
        target_relative_path=target_relative_path,
        source_relative_path="Ask",
        reason=reason,
        current_content=old_content,
        proposed_content=proposed_content,
        citations=citations,
    )
    review_path = vault_path / review_relative_path
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(review_content, encoding="utf-8")

    conn.execute(
        """
        INSERT INTO proposed_updates(
          id, wiki_page_id, source_file_id, source_relative_path, source_sha256, target_relative_path, target_title,
          old_content, proposed_content, reason, confidence, source_citations_json, review_path, ingest_run_id, model,
          target_sha256_at_creation, status, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            proposal_id,
            page_row["id"],
            None,
            "Ask",
            None,
            target_relative_path,
            target_title,
            old_content,
            proposed_content,
            reason,
            "medium",
            json.dumps(source_citations, ensure_ascii=False),
            review_relative_path.as_posix(),
            "ask",
            "ask",
            sha256_text(old_content),
            "pending",
        ),
    )
    return {"proposal_id": proposal_id, "review_path": review_relative_path.as_posix()}


def search_wiki_pages(conn, *, query: str, limit: int) -> list[AskCitationItem]:
    fts_query = _fts_query(query)
    if not fts_query:
        return []
    rows = conn.execute(
        """
        SELECT
          wiki_pages.relative_path,
          wiki_pages.title,
          wiki_pages_fts.content,
          bm25(wiki_pages_fts, 2.0, 1.0, 0.4) AS score
        FROM wiki_pages_fts
        JOIN wiki_pages ON wiki_pages.id = wiki_pages_fts.wiki_page_id
        WHERE wiki_pages_fts MATCH ?
        ORDER BY score ASC
        LIMIT ?
        """,
        (fts_query, limit),
    ).fetchall()
    return [
        AskCitationItem(
            citation_id=f"W{index + 1}",
            kind="wiki",
            path=row["relative_path"],
            title=row["title"],
            content=row["content"] or "",
        )
        for index, row in enumerate(rows)
    ]


def load_graph_neighbors(conn, *, vault_path: Path, wiki_hits: list[AskCitationItem], limit: int) -> list[AskCitationItem]:
    if not wiki_hits:
        return []
    link_titles: list[str] = []
    for hit in wiki_hits:
        for match in re.findall(r"\[\[([^\]]+)\]\]", hit.content):
            candidate = match.strip()
            if candidate:
                link_titles.append(candidate)
    if not link_titles:
        return []
    seen = set()
    neighbors: list[AskCitationItem] = []
    for title in link_titles:
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        row = conn.execute(
            """
            SELECT relative_path, title, summary
            FROM wiki_pages
            WHERE lower(title) = lower(?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (title,),
        ).fetchone()
        if row is None:
            continue
        page_path = vault_path / row["relative_path"]
        if not page_path.exists():
            continue
        neighbors.append(
            AskCitationItem(
                citation_id=f"WN{len(neighbors) + 1}",
                kind="wiki",
                path=row["relative_path"],
                title=row["title"],
                content=page_path.read_text(encoding="utf-8"),
            )
        )
        if len(neighbors) >= limit:
            break
    return neighbors


def search_raw_chunks(conn, *, query: str, limit: int) -> list[AskCitationItem]:
    fts_query = _fts_query(query)
    if not fts_query:
        return []
    rows = conn.execute(
        """
        SELECT relative_path, text, heading, page_number, line_start, line_end
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY bm25(chunks_fts)
        LIMIT ?
        """,
        (fts_query, limit),
    ).fetchall()
    result: list[AskCitationItem] = []
    for index, row in enumerate(rows):
        locator_bits: list[str] = []
        if row["heading"]:
            locator_bits.append(f"heading {row['heading']}")
        if row["page_number"] is not None:
            locator_bits.append(f"p.{row['page_number']}")
        if row["line_start"] is not None and row["line_end"] is not None:
            locator_bits.append(f"lines {row['line_start']}-{row['line_end']}")
        result.append(
            AskCitationItem(
                citation_id=f"R{index + 1}",
                kind="raw",
                path=row["relative_path"],
                locator=", ".join(locator_bits) if locator_bits else None,
                content=row["text"] or "",
            )
        )
    return result


def dedupe_pages(items: list[AskCitationItem]) -> list[AskCitationItem]:
    seen = set()
    deduped: list[AskCitationItem] = []
    for item in items:
        key = (item.kind, item.path.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _generate_answer(*, provider: LLMProvider, question: str, evidence: list[AskCitationItem]) -> dict:
    allowed_ids = [item.citation_id for item in evidence]
    payload = provider.complete_structured(
        system_prompt=ASK_PROMPT,
        user_prompt=json.dumps(
            {
                "question": question,
                "evidence": [
                    {
                        "citation_id": item.citation_id,
                        "kind": item.kind,
                        "path": item.path,
                        "title": item.title,
                        "locator": item.locator,
                        "content": item.content[:2400],
                    }
                    for item in evidence
                ],
            },
            ensure_ascii=False,
        ),
        schema=ask_answer_schema(),
    )
    parsed = parse_ask_answer(payload)
    for citation_id in parsed["citation_ids"]:
        if citation_id not in allowed_ids:
            raise LLMOutputError(f"Unsupported citation id from model: {citation_id}")
    return parsed


def ask_answer_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "answer": {"type": "string", "minLength": 1},
            "unsupported": {"type": "boolean"},
            "citation_ids": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
            },
        },
        "required": ["answer", "unsupported", "citation_ids"],
    }


def parse_ask_answer(payload: dict | str) -> dict:
    raw = payload
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines)
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise LLMOutputError("Ask output must be a JSON object.")
    answer = str(raw.get("answer", "")).strip()
    if not answer:
        raise LLMOutputError("Ask output is missing answer.")
    citation_ids = raw.get("citation_ids", [])
    if not isinstance(citation_ids, list) or not all(isinstance(item, str) and item.strip() for item in citation_ids):
        raise LLMOutputError("Ask output has invalid citation_ids.")
    return {
        "answer": answer,
        "unsupported": bool(raw.get("unsupported", False)),
        "citation_ids": [item.strip() for item in citation_ids],
    }


def _fts_query(text: str) -> str:
    tokens = [token.strip().lower() for token in re.findall(r"[A-Za-z0-9_]+", text)]
    tokens = [token for token in tokens if len(token) > 2]
    if not tokens:
        return ""
    deduped: list[str] = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= 8:
            break
    return " OR ".join(deduped)


ASK_PROMPT = """You answer user questions using provided wiki and raw evidence.

Rules:
- Prefer wiki evidence. Use raw evidence only for grounding/verification.
- If evidence is insufficient, return unsupported=true and explain briefly.
- Do not fabricate citations. Only cite provided citation_ids.
- Keep answer concise and directly relevant.
- Return JSON only.
"""
