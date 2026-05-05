from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llm_wiki_backend.ingestion.extractors import extract_file, supported_file_type
from llm_wiki_backend.main import app

client = TestClient(app)


@pytest.fixture
def vault_path() -> Path:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"vault-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        response = client.post("/ingest/raw/watch/stop")
        assert response.status_code == 200
        shutil.rmtree(path, ignore_errors=True)


def _bootstrap(vault_path: Path) -> None:
    response = client.post("/vault/bootstrap", json={"path": str(vault_path)})
    assert response.status_code == 200


def test_feature24_markdown_headings_detected_in_extractor() -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"feature24-{uuid.uuid4().hex}.md"
    try:
        path.write_text("# Title\n\n## Section A\n\nBody paragraph.\n", encoding="utf-8")
        file_type = supported_file_type(path)
        assert file_type == "text"

        extraction = extract_file(path, file_type)
        assert extraction is not None
        assert extraction.title == "Title"
        assert extraction.metadata["headings"] == ["Title", "Section A"]
        assert len(extraction.chunks) >= 1
        assert extraction.chunks[0].heading == "Title"
    finally:
        path.unlink(missing_ok=True)


def test_feature24_markdown_headings_persisted_to_sqlite(vault_path: Path) -> None:
    _bootstrap(vault_path)
    note = vault_path / "Raw" / "headings.md"
    note.write_text("# Title\n\n## Section A\n\nBody paragraph.\n", encoding="utf-8")

    run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert run.status_code == 200

    db_path = vault_path / ".llm-wiki" / "app.db"
    with sqlite3.connect(db_path) as conn:
        extraction_row = conn.execute(
            """
            SELECT e.title, e.extraction_metadata_json
            FROM extractions e
            JOIN files f ON f.id = e.file_id
            WHERE f.relative_path = 'Raw/headings.md'
            """
        ).fetchone()
        assert extraction_row is not None
        assert extraction_row[0] == "Title"
        metadata = json.loads(extraction_row[1])
        assert metadata["headings"] == ["Title", "Section A"]

        heading_rows = conn.execute(
            """
            SELECT c.heading
            FROM chunks c
            JOIN extractions e ON e.id = c.extraction_id
            JOIN files f ON f.id = e.file_id
            WHERE f.relative_path = 'Raw/headings.md'
            """
        ).fetchall()
        assert heading_rows
        assert heading_rows[0][0] == "Title"
