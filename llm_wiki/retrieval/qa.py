from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from llm_wiki.retrieval.search import RetrievalHit, search_generated_summaries, search_raw_chunks


@dataclass(frozen=True)
class QAResult:
    question: str
    answer: str
    citations: list[str]
    supported: bool


def answer_question(
    connection: sqlite3.Connection,
    vault_root: Path,
    question: str,
) -> QAResult:
    summary_hits = search_generated_summaries(connection, vault_root, question, limit=3)
    chunk_hits = search_raw_chunks(connection, question, limit=5)
    if not summary_hits and not chunk_hits:
        return QAResult(
            question=question,
            answer="Not supported by the current sources.",
            citations=[],
            supported=False,
        )

    all_hits = _merge_hits(summary_hits, chunk_hits)
    citations = [hit.citation for hit in all_hits]
    evidence_lines = [f"- {hit.citation}: {hit.text}" for hit in all_hits[:4]]
    answer = (
        "Grounded answer based on retrieved sources:\n\n"
        + "\n".join(evidence_lines)
        + "\n\n"
        + "If you need a tighter answer, refine the question with specific terms."
    )
    return QAResult(question=question, answer=answer, citations=citations, supported=True)


def render_qa_markdown(result: QAResult) -> str:
    lines = [
        f"# Q&A: {result.question}",
        "",
        "## Answer",
        "",
        result.answer,
        "",
        "## Sources",
        "",
    ]
    if result.citations:
        for citation in result.citations:
            lines.append(f"- {citation}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _merge_hits(summary_hits: list[RetrievalHit], chunk_hits: list[RetrievalHit]) -> list[RetrievalHit]:
    combined = summary_hits + chunk_hits
    combined.sort(key=lambda hit: (hit.score, 1 if hit.source_type == "raw_chunk" else 0), reverse=True)
    return combined
