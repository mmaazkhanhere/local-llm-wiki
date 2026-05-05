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


def test_feature27_html_extractor_filters_noise_and_keeps_readable_content() -> None:
    root = Path(__file__).resolve().parents[1] / ".test-work"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"feature27-{uuid.uuid4().hex}.html"
    html_text = (
        "<html><head><title>Article Title</title><style>noise-style</style></head>"
        "<body><nav>noise-nav</nav><h1>Body Heading</h1><p>Keep me</p>"
        "<script>noise-script</script></body></html>"
    )
    try:
        path.write_text(html_text, encoding="utf-8")
        file_type = supported_file_type(path)
        assert file_type == "html"

        extraction = extract_file(path, file_type)
        assert extraction is not None
        assert extraction.title == "Article Title"
        assert extraction.metadata["title"] == "Article Title"
        assert "Body Heading" in extraction.text
        assert "Keep me" in extraction.text
        assert "noise-nav" not in extraction.text
        assert "noise-script" not in extraction.text
        assert "noise-style" not in extraction.text
    finally:
        path.unlink(missing_ok=True)


def test_feature27_html_persists_title_and_filters_noise_in_sqlite(vault_path: Path) -> None:
    _bootstrap(vault_path)
    html_path = vault_path / "Raw" / "sample.html"
    html_path.write_text(
        "<html><head><title>Article Title</title><style>noise-style</style></head>"
        "<body><nav>noise-nav</nav><h1>Body Heading</h1><p>Keep me</p>"
        "<script>noise-script</script></body></html>",
        encoding="utf-8",
    )

    run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert run.status_code == 200

    db_path = vault_path / ".llm-wiki" / "app.db"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT e.title, e.extracted_text, e.extraction_metadata_json
            FROM extractions e
            JOIN files f ON f.id = e.file_id
            WHERE f.relative_path = 'Raw/sample.html'
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "Article Title"
        assert "Body Heading" in row[1]
        assert "Keep me" in row[1]
        assert "noise-nav" not in row[1]
        assert "noise-script" not in row[1]
        assert "noise-style" not in row[1]
        metadata = json.loads(row[2])
        assert metadata["kind"] == "html"
        assert metadata["title"] == "Article Title"

        fts_text = conn.execute(
            """
            SELECT GROUP_CONCAT(text, ' ')
            FROM chunks_fts
            WHERE relative_path = 'Raw/sample.html'
            """
        ).fetchone()[0]
        assert fts_text is not None
        assert "Body Heading" in fts_text
        assert "Keep me" in fts_text
