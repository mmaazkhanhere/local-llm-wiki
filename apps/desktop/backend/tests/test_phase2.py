from __future__ import annotations

import hashlib
import shutil
import sqlite3
import time
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


def _write_sample_pdf(path: Path) -> None:
    pdf_bytes = b"""%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n4 0 obj<</Length 52>>stream\nBT\n/F1 24 Tf\n72 720 Td\n(Phase Two PDF line) Tj\nET\nendstream\nendobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000063 00000 n \n0000000120 00000 n \n0000000244 00000 n \n0000000347 00000 n \ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n417\n%%EOF"""
    path.write_bytes(pdf_bytes)


def _write_sample_docx(path: Path) -> None:
    document_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
  <w:body>
    <w:p><w:pPr><w:pStyle w:val='Heading1'/></w:pPr><w:r><w:t>Docx Heading</w:t></w:r></w:p>
    <w:p><w:r><w:t>Docx paragraph text.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def _wait_for(predicate, timeout_seconds: float = 4.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for condition")


def test_raw_scan_discovers_files_and_ignores_protected_paths(vault_path: Path) -> None:
    _bootstrap(vault_path)
    raw = vault_path / "Raw"
    (raw / "keep.md").write_text("# Keep", encoding="utf-8")
    (raw / "keep.txt").write_text("Hello", encoding="utf-8")

    (raw / ".git").mkdir(parents=True)
    (raw / ".git" / "skip.txt").write_text("skip", encoding="utf-8")
    (raw / "Wiki").mkdir(parents=True)
    (raw / "Wiki" / "skip.md").write_text("skip", encoding="utf-8")
    (raw / ".llm-wiki").mkdir(parents=True)
    (raw / ".llm-wiki" / "skip.md").write_text("skip", encoding="utf-8")

    scan = client.post("/ingest/raw/scan", params={"vault_path": str(vault_path)})
    assert scan.status_code == 200
    assert scan.json()["discovered_count"] == 2

    inbox = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)})
    assert inbox.status_code == 200
    files = inbox.json()["files"]
    rel_paths = {item["relative_path"] for item in files}
    assert rel_paths == {"Raw/keep.md", "Raw/keep.txt"}


def test_hash_reprocessing_is_hash_based(vault_path: Path) -> None:
    _bootstrap(vault_path)
    source = vault_path / "Raw" / "rehash.txt"
    source.write_text("first", encoding="utf-8")

    run1 = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert run1.status_code == 200

    inbox1 = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)}).json()["files"]
    row1 = next(item for item in inbox1 if item["relative_path"] == "Raw/rehash.txt")
    original_hash = row1["sha256"]
    assert row1["processing_status"] == "processed"

    hash_unchanged = client.post("/ingest/raw/hash", params={"vault_path": str(vault_path)})
    assert hash_unchanged.status_code == 200
    assert hash_unchanged.json()["skipped_count"] >= 1

    source.write_text("second", encoding="utf-8")
    hash_changed = client.post("/ingest/raw/hash", params={"vault_path": str(vault_path)})
    assert hash_changed.status_code == 200
    assert hash_changed.json()["queued_count"] >= 1

    process = client.post("/ingest/raw/process", params={"vault_path": str(vault_path)})
    assert process.status_code == 200
    assert process.json()["processed_count"] >= 1

    inbox2 = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)}).json()["files"]
    row2 = next(item for item in inbox2 if item["relative_path"] == "Raw/rehash.txt")
    assert row2["sha256"] != original_hash
    assert row2["processing_status"] == "processed"


def test_phase2_extraction_and_fts_storage(vault_path: Path) -> None:
    _bootstrap(vault_path)
    raw = vault_path / "Raw"

    (raw / "note.md").write_text("# Heading\n\nAlpha content", encoding="utf-8")
    (raw / "plain.txt").write_text("Plain text source", encoding="utf-8")
    _write_sample_pdf(raw / "sample.pdf")
    _write_sample_docx(raw / "sample.docx")
    (raw / "sample.html").write_text(
        "<html><head><title>T</title><style>x</style></head><body><nav>skip</nav><h1>Body</h1><p>Keep me</p><script>skip</script></body></html>",
        encoding="utf-8",
    )
    (raw / "code.py").write_text("def x():\n    return 1\n", encoding="utf-8")
    (raw / "data.json").write_text('{"k": "v"}', encoding="utf-8")
    (raw / "data.yaml").write_text("name: test\n", encoding="utf-8")
    (raw / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (raw / "image.jpg").write_bytes(b"not-a-real-jpg")

    before_hashes = {
        p.relative_to(raw).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in raw.rglob("*")
        if p.is_file()
    }

    run = client.post("/ingest/raw/run", params={"vault_path": str(vault_path)})
    assert run.status_code == 200

    inbox = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)})
    assert inbox.status_code == 200
    rows = {item["relative_path"]: item for item in inbox.json()["files"]}

    assert rows["Raw/image.jpg"]["processing_status"] == "pending_image"
    assert rows["Raw/note.md"]["processing_status"] == "processed"
    assert rows["Raw/plain.txt"]["processing_status"] == "processed"
    assert rows["Raw/sample.pdf"]["processing_status"] in {"processed", "extraction_limited"}
    assert rows["Raw/sample.docx"]["processing_status"] == "processed"
    assert rows["Raw/sample.html"]["processing_status"] == "processed"
    assert rows["Raw/code.py"]["processing_status"] == "processed"
    assert rows["Raw/data.json"]["processing_status"] == "processed"
    assert rows["Raw/data.yaml"]["processing_status"] == "processed"
    assert rows["Raw/data.csv"]["processing_status"] == "processed"

    after_hashes = {
        p.relative_to(raw).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in raw.rglob("*")
        if p.is_file()
    }
    assert after_hashes == before_hashes

    db_path = vault_path / ".llm-wiki" / "app.db"
    with sqlite3.connect(db_path) as conn:
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        image_extractions = conn.execute(
            """
            SELECT COUNT(*)
            FROM extractions e
            JOIN files f ON f.id = e.file_id
            WHERE f.relative_path = 'Raw/image.jpg'
            """
        ).fetchone()[0]
    assert chunk_count > 0
    assert fts_count > 0
    assert image_extractions == 0


def test_raw_watcher_create_change_and_exclusions(vault_path: Path) -> None:
    _bootstrap(vault_path)

    start = client.post(
        "/ingest/raw/watch/start",
        params={
            "vault_path": str(vault_path),
            "poll_interval_seconds": 0.05,
            "stabilize_seconds": 0.25,
        },
    )
    assert start.status_code == 200
    assert start.json()["running"] is True

    watched = vault_path / "Raw" / "watched.txt"
    watched.write_text("line 1", encoding="utf-8")
    time.sleep(0.1)
    watched.write_text("line 1\nline 2", encoding="utf-8")

    excluded_dir = vault_path / "Raw" / "Wiki"
    excluded_dir.mkdir(parents=True, exist_ok=True)
    (excluded_dir / "skip.md").write_text("skip me", encoding="utf-8")

    def watched_processed() -> bool:
        response = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)})
        if response.status_code != 200:
            return False
        files = {item["relative_path"]: item for item in response.json()["files"]}
        row = files.get("Raw/watched.txt")
        if row is None:
            return False
        return row["processing_status"] in {"processed", "extraction_limited"}

    _wait_for(watched_processed, timeout_seconds=8.0)

    unsupported = vault_path / "Raw" / "blob.bin"
    unsupported.write_bytes(b"\x00\x01binary")

    def unsupported_discovered() -> bool:
        response = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)})
        if response.status_code != 200:
            return False
        files = {item["relative_path"]: item for item in response.json()["files"]}
        row = files.get("Raw/blob.bin")
        if row is None:
            return False
        return row["processing_status"] == "unsupported"

    _wait_for(unsupported_discovered, timeout_seconds=8.0)

    inbox = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)})
    rows = {item["relative_path"]: item for item in inbox.json()["files"]}
    assert "Raw/watched.txt" in rows
    assert rows["Raw/blob.bin"]["processing_status"] == "unsupported"
    assert "Raw/Wiki/skip.md" not in rows

    before_hash = rows["Raw/watched.txt"]["sha256"]
    watched.write_text("line 1\nline 2\nline 3", encoding="utf-8")

    def watched_reprocessed() -> bool:
        response = client.get("/ingest/raw/inbox", params={"vault_path": str(vault_path)})
        if response.status_code != 200:
            return False
        files = {item["relative_path"]: item for item in response.json()["files"]}
        row = files.get("Raw/watched.txt")
        if row is None:
            return False
        return row["sha256"] != before_hash and row["processing_status"] in {"processed", "extraction_limited"}

    _wait_for(watched_reprocessed)

    stop = client.post("/ingest/raw/watch/stop")
    assert stop.status_code == 200
    assert stop.json()["running"] is False
