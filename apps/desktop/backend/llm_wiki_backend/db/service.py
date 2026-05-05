from __future__ import annotations

import sqlite3
from pathlib import Path


def initialize_database(vault_path: Path) -> Path:
    db_path = vault_path / ".llm-wiki" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(_schema_sql())
        conn.executescript(_phase2_schema_sql())
        conn.commit()
    return db_path


def connect_database(vault_path: Path) -> sqlite3.Connection:
    db_path = initialize_database(vault_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def clear_all_runtime_data(vault_path: Path) -> None:
    with connect_database(vault_path) as conn:
        conn.execute("DELETE FROM chunks_fts;")
        conn.execute("DELETE FROM chunks;")
        conn.execute("DELETE FROM extractions;")
        conn.execute("DELETE FROM files;")
        conn.execute("DELETE FROM wiki_pages;")
        conn.execute("DELETE FROM proposed_updates;")
        conn.execute("DELETE FROM audit_events;")
        conn.execute("DELETE FROM flashcards;")
        conn.execute("DELETE FROM review_items;")
        conn.commit()


def _schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS vaults (
      id TEXT PRIMARY KEY,
      path TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_opened_at TEXT
    );
    CREATE TABLE IF NOT EXISTS files (
      id TEXT PRIMARY KEY,
      vault_id TEXT NOT NULL,
      path TEXT NOT NULL,
      relative_path TEXT NOT NULL,
      file_type TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      size_bytes INTEGER,
      created_at TEXT,
      modified_at TEXT,
      last_seen_at TEXT,
      processing_status TEXT NOT NULL,
      last_processed_at TEXT,
      error_message TEXT
    );
    CREATE TABLE IF NOT EXISTS extractions (
      id TEXT PRIMARY KEY,
      file_id TEXT NOT NULL,
      title TEXT,
      extracted_text TEXT,
      extraction_metadata_json TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS chunks (
      id TEXT PRIMARY KEY,
      extraction_id TEXT NOT NULL,
      chunk_index INTEGER NOT NULL,
      text TEXT NOT NULL,
      token_count INTEGER,
      page_number INTEGER,
      heading TEXT,
      metadata_json TEXT
    );
    CREATE TABLE IF NOT EXISTS wiki_pages (
      id TEXT PRIMARY KEY,
      extraction_id TEXT,
      page_type TEXT NOT NULL,
      path TEXT NOT NULL,
      relative_path TEXT NOT NULL,
      sha256 TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      status TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS proposed_updates (
      id TEXT PRIMARY KEY,
      wiki_page_id TEXT NOT NULL,
      old_content TEXT NOT NULL,
      proposed_content TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      resolved_at TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_events (
      id TEXT PRIMARY KEY,
      event_type TEXT NOT NULL,
      target_path TEXT,
      source_paths_json TEXT,
      summary TEXT NOT NULL,
      details_json TEXT,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS flashcards (
      id TEXT PRIMARY KEY,
      extraction_id TEXT NOT NULL,
      question TEXT NOT NULL,
      answer TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS review_items (
      id TEXT PRIMARY KEY,
      extraction_id TEXT,
      title TEXT NOT NULL,
      issue TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      resolved_at TEXT
    );
    """


def _phase2_schema_sql() -> str:
    return """
    CREATE INDEX IF NOT EXISTS idx_files_vault_relative_path
      ON files(vault_id, relative_path);
    CREATE INDEX IF NOT EXISTS idx_files_status
      ON files(processing_status);
    CREATE INDEX IF NOT EXISTS idx_extractions_file
      ON extractions(file_id);
    CREATE INDEX IF NOT EXISTS idx_chunks_extraction
      ON chunks(extraction_id);

    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
      chunk_id UNINDEXED,
      extraction_id UNINDEXED,
      file_id UNINDEXED,
      relative_path UNINDEXED,
      text,
      heading,
      page_number UNINDEXED,
      line_start UNINDEXED,
      line_end UNINDEXED
    );
    """
