from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from llm_wiki_backend.core.errors import WikiGenerationError
from llm_wiki_backend.wiki.models import FlashcardCandidate, WikiCandidate

PAGE_DIRECTORIES = {
    "concept": Path("Wiki/Concepts"),
    "entity": Path("Wiki/Entities"),
    "comparison": Path("Wiki/Comparisons"),
    "map": Path("Wiki/Maps"),
}

INDEX_HEADINGS = {
    "concept": "## Concepts",
    "entity": "## Entities",
    "comparison": "## Comparisons",
    "map": "## Maps",
}


def safe_markdown_filename(title: str) -> str:
    normalized = re.sub(r"[<>:\"/\\|?*\x00-\x1F]+", " ", title).strip()
    normalized = re.sub(r"\s+", " ", normalized).strip(". ")
    if not normalized:
        raise WikiGenerationError("Wiki page title produced an unsafe filename.")
    return f"{normalized}.md"


def render_page(candidate: WikiCandidate, source_relative_path: str) -> str:
    sections = [f"# {candidate.title}", "", candidate.summary.strip(), "", candidate.content_markdown.strip()]
    if candidate.wiki_links:
        sections.extend(["", "## Related", ""])
        for link in candidate.wiki_links:
            sections.append(f"- [[{link}]]")
    sections.extend(["", "## Sources", ""])
    for source in candidate.sources:
        sections.append(f"- Source: `{source_relative_path}`, {source.locator}")
    return "\n".join(sections).strip() + "\n"


def render_flashcards(title: str, cards: list[FlashcardCandidate], source_relative_path: str) -> str:
    lines = [f"# Flashcards: {title}", "", "## Cards", ""]
    for index, card in enumerate(cards, start=1):
        lines.extend([f"### {index}. {card.question}", "", card.answer.strip(), ""])
        for source in card.sources:
            lines.append(f"Source: `{source_relative_path}`, {source.locator}")
        lines.extend(["", "---", ""])
    return "\n".join(lines).strip() + "\n"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def title_exists_anywhere(vault_path: Path, title: str) -> bool:
    expected_name = safe_markdown_filename(title).lower()
    wiki_root = vault_path / "Wiki"
    for file_path in wiki_root.rglob("*.md"):
        if file_path.name.lower() == expected_name:
            return True
    return False


def update_index(index_path: Path, entries: list[tuple[str, str, str]]) -> bool:
    if not entries:
        return False
    content = index_path.read_text(encoding="utf-8") if index_path.exists() else "# Wiki Index\n"
    lines = content.splitlines()
    updated = False
    for page_type, title, summary in entries:
        heading = INDEX_HEADINGS[page_type]
        bullet = f"- [[{title}]] — {summary}"
        if bullet in lines:
            continue
        try:
            insert_at = lines.index(heading) + 1
        except ValueError as exc:
            raise WikiGenerationError(f"Missing index heading: {heading}") from exc
        while insert_at < len(lines) and lines[insert_at].startswith("- [["):
            insert_at += 1
        lines.insert(insert_at, bullet)
        updated = True
    if updated:
        atomic_write_text(index_path, "\n".join(lines).rstrip() + "\n")
    return updated


def append_log(log_path: Path, source_relative_path: str, generated_pages: list[str], status: str) -> bool:
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        f"- {timestamp} | source=`{source_relative_path}` | status={status} | pages={', '.join(generated_pages) if generated_pages else 'none'}"
    ]
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Processing Log\n"
    content = existing.rstrip() + "\n" + "\n".join(lines) + "\n"
    atomic_write_text(log_path, content)
    return True
