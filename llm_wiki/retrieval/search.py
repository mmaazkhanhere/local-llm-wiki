from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RetrievalHit:
    source_type: str
    citation: str
    text: str
    score: int


def search_generated_summaries(
    connection: sqlite3.Connection,
    vault_root: Path,
    query: str,
    limit: int = 5,
) -> list[RetrievalHit]:
    rows = connection.execute(
        """
        SELECT relative_path, path
        FROM generated_pages
        WHERE page_type = 'source_summary'
        """,
    ).fetchall()
    tokens = _tokenize(query)
    hits: list[RetrievalHit] = []
    for row in rows:
        path = Path(row["path"])
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        score = _score_text(text, tokens)
        if score <= 0:
            continue
        hits.append(
            RetrievalHit(
                source_type="summary",
                citation=f"`{row['relative_path']}`",
                text=_snippet(text),
                score=score,
            )
        )
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]


def search_raw_chunks(
    connection: sqlite3.Connection,
    query: str,
    limit: int = 8,
) -> list[RetrievalHit]:
    rows = connection.execute(
        """
        SELECT f.relative_path, c.chunk_index, c.text
        FROM chunks c
        JOIN source_documents sd ON sd.id = c.source_document_id
        JOIN files f ON f.id = sd.file_id
        ORDER BY f.relative_path ASC, c.chunk_index ASC
        """
    ).fetchall()
    tokens = _tokenize(query)
    hits: list[RetrievalHit] = []
    for row in rows:
        text = row["text"] or ""
        score = _score_text(text, tokens)
        if score <= 0:
            continue
        citation = f"`{row['relative_path']}`, chunk {row['chunk_index']}"
        hits.append(
            RetrievalHit(
                source_type="raw_chunk",
                citation=citation,
                text=_snippet(text),
                score=score,
            )
        )
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_text(text: str, tokens: set[str]) -> int:
    if not tokens:
        return 0
    lower = text.lower()
    return sum(1 for token in tokens if token in lower)


def _snippet(text: str, max_len: int = 360) -> str:
    condensed = " ".join(text.split())
    return condensed[:max_len]
