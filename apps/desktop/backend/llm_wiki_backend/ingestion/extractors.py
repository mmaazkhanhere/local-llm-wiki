from __future__ import annotations

import csv
import html
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from llm_wiki_backend.ingestion.types import ChunkDraft, ExtractionDraft

TEXT_EXTENSIONS = {".md", ".txt"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
HTML_EXTENSIONS = {".html", ".htm"}
CODE_AND_STRUCTURED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".cs",
    ".go",
    ".rs",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

MAX_CHUNK_CHARS = 1500
MAX_LINES_PER_CHUNK = 80


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_title = False
        self._ignored_depth = 0
        self.title: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._inside_title = True
            return
        if lowered in {"script", "style", "nav", "header", "footer", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._inside_title = False
            return
        if lowered in {"script", "style", "nav", "header", "footer", "noscript"} and self._ignored_depth > 0:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        content = data.strip()
        if not content:
            return
        if self._inside_title:
            self.title = content
            return
        if self._ignored_depth > 0:
            return
        self._text_parts.append(content)

    def combined_text(self) -> str:
        return "\n".join(self._text_parts)


def supported_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in DOCX_EXTENSIONS:
        return "docx"
    if suffix in HTML_EXTENSIONS:
        return "html"
    if suffix in CODE_AND_STRUCTURED_EXTENSIONS:
        return "code"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "unsupported"


def extract_file(path: Path, file_type: str) -> ExtractionDraft | None:
    if file_type == "text":
        return _extract_text_or_markdown(path)
    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type == "docx":
        return _extract_docx(path)
    if file_type == "html":
        return _extract_html(path)
    if file_type == "code":
        return _extract_code_or_structured(path)
    return None


def _extract_text_or_markdown(path: Path) -> ExtractionDraft:
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = _normalize_text(text)
    headings = _parse_markdown_headings(normalized) if path.suffix.lower() == ".md" else []
    title = headings[0] if headings else _first_non_empty_line(normalized)
    chunks = _chunk_plain_text(normalized, headings=headings)
    return ExtractionDraft(
        title=title,
        text=normalized,
        metadata={"kind": "text", "headings": headings},
        chunks=chunks,
        limited=False,
    )


def _extract_pdf(path: Path) -> ExtractionDraft:
    try:
        pages = _extract_pdf_with_pypdf(path)
    except Exception:
        pages = _extract_pdf_naive(path)

    if not pages:
        return ExtractionDraft(
            title=path.stem,
            text="",
            metadata={"kind": "pdf", "limited_reason": "no_extractable_text"},
            chunks=[],
            limited=True,
        )

    page_chunks: list[ChunkDraft] = []
    page_texts: list[str] = []
    for index, page_text in enumerate(pages, start=1):
        normalized = _normalize_text(page_text)
        if not normalized.strip():
            continue
        page_texts.append(normalized)
        for chunk in _chunk_plain_text(normalized):
            page_chunks.append(
                ChunkDraft(
                    text=chunk.text,
                    heading=chunk.heading,
                    page_number=index,
                    line_start=None,
                    line_end=None,
                )
            )

    full_text = "\n\n".join(page_texts)
    limited = len(page_chunks) == 0
    return ExtractionDraft(
        title=path.stem,
        text=full_text,
        metadata={"kind": "pdf", "page_count": len(pages)},
        chunks=page_chunks,
        limited=limited,
    )


def _extract_docx(path: Path) -> ExtractionDraft:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    lines: list[str] = []
    headings: list[str] = []

    for paragraph in root.findall(".//w:p", namespace):
        style = _paragraph_style(paragraph, namespace)
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        value = "".join(texts).strip()
        if not value:
            continue
        if style.startswith("Heading"):
            headings.append(value)
            lines.append(f"# {value}")
        else:
            lines.append(value)

    table_values: list[str] = []
    for table in root.findall(".//w:tbl", namespace):
        for row in table.findall(".//w:tr", namespace):
            cells = []
            for cell in row.findall(".//w:tc", namespace):
                cell_text = " ".join(node.text or "" for node in cell.findall(".//w:t", namespace)).strip()
                if cell_text:
                    cells.append(cell_text)
            if cells:
                table_values.append(" | ".join(cells))

    if table_values:
        lines.append("")
        lines.extend(table_values)

    text = _normalize_text("\n".join(lines))
    title = headings[0] if headings else path.stem
    chunks = _chunk_plain_text(text, headings=headings)

    return ExtractionDraft(
        title=title,
        text=text,
        metadata={"kind": "docx", "headings": headings, "table_rows": len(table_values)},
        chunks=chunks,
        limited=False,
    )


def _extract_html(path: Path) -> ExtractionDraft:
    raw = path.read_text(encoding="utf-8", errors="replace")
    parser = _ReadableHtmlParser()
    parser.feed(raw)

    title = parser.title or path.stem
    text = _normalize_text(parser.combined_text())
    chunks = _chunk_plain_text(text)

    return ExtractionDraft(
        title=title,
        text=text,
        metadata={"kind": "html", "title": title},
        chunks=chunks,
        limited=not bool(text.strip()),
    )


def _extract_code_or_structured(path: Path) -> ExtractionDraft:
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = _normalize_text(text)

    if path.suffix.lower() == ".csv":
        normalized = _normalize_csv(normalized)

    chunks = _chunk_with_line_numbers(normalized)
    return ExtractionDraft(
        title=path.stem,
        text=normalized,
        metadata={"kind": "code_or_structured", "line_references": True},
        chunks=chunks,
        limited=False,
    )


def _extract_pdf_with_pypdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - fallback path handles this.
        raise RuntimeError("pypdf_unavailable") from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return pages


def _extract_pdf_naive(path: Path) -> list[str]:
    data = path.read_bytes()
    streams = re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.DOTALL)
    page_text: list[str] = []

    for stream in streams:
        for match in re.findall(rb"\((.*?)\)\s*Tj", stream, flags=re.DOTALL):
            parsed = _decode_pdf_literal(match)
            if parsed:
                page_text.append(parsed)
        for array_body in re.findall(rb"\[(.*?)\]\s*TJ", stream, flags=re.DOTALL):
            for match in re.findall(rb"\((.*?)\)", array_body, flags=re.DOTALL):
                parsed = _decode_pdf_literal(match)
                if parsed:
                    page_text.append(parsed)

    if not page_text:
        return []

    return ["\n".join(page_text)]


def _decode_pdf_literal(value: bytes) -> str:
    escaped = value.replace(rb"\\n", b"\n").replace(rb"\\r", b"\n").replace(rb"\\t", b"\t")
    escaped = escaped.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\\\", b"\\")
    decoded = escaped.decode("latin-1", errors="ignore")
    return html.unescape(decoded).strip()


def _paragraph_style(paragraph: ET.Element, namespace: dict[str, str]) -> str:
    props = paragraph.find("w:pPr", namespace)
    if props is None:
        return ""
    style = props.find("w:pStyle", namespace)
    if style is None:
        return ""
    value = style.get(f"{{{namespace['w']}}}val")
    return value or ""


def _parse_markdown_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            if heading_text:
                headings.append(heading_text)
    return headings


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def _normalize_csv(text: str) -> str:
    reader = csv.reader(io.StringIO(text))
    lines = [", ".join(cell.strip() for cell in row) for row in reader]
    return _normalize_text("\n".join(lines))


def _chunk_plain_text(text: str, headings: list[str] | None = None) -> list[ChunkDraft]:
    if not text:
        return []

    chunks: list[ChunkDraft] = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [line for line in text.splitlines() if line.strip()]

    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= MAX_CHUNK_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(ChunkDraft(text=current))
        if len(paragraph) <= MAX_CHUNK_CHARS:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            end = start + MAX_CHUNK_CHARS
            chunk_text = paragraph[start:end].strip()
            if chunk_text:
                chunks.append(ChunkDraft(text=chunk_text))
            start = end
        current = ""

    if current:
        chunks.append(ChunkDraft(text=current))

    if headings:
        heading_cycle = iter(headings)
        heading_value = next(heading_cycle, None)
        decorated: list[ChunkDraft] = []
        for chunk in chunks:
            decorated.append(ChunkDraft(text=chunk.text, heading=heading_value))
            heading_value = next(heading_cycle, heading_value)
        return decorated

    return chunks


def _chunk_with_line_numbers(text: str) -> list[ChunkDraft]:
    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[ChunkDraft] = []
    start_index = 0
    while start_index < len(lines):
        end_index = min(start_index + MAX_LINES_PER_CHUNK, len(lines))
        chunk_lines = lines[start_index:end_index]
        chunk_text = "\n".join(chunk_lines).strip()
        if chunk_text:
            chunks.append(
                ChunkDraft(
                    text=chunk_text,
                    line_start=start_index + 1,
                    line_end=end_index,
                )
            )
        start_index = end_index

    return chunks
