# Database Schema

This file mirrors the backend SQLite schema in `apps/desktop/backend/llm_wiki_backend/db/service.py`.

## Tables

### `vaults`

```sql
CREATE TABLE vaults (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_opened_at TEXT
);
```

### `files`

```sql
CREATE TABLE files (
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
```

### `extractions`

```sql
CREATE TABLE extractions (
  id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  title TEXT,
  extracted_text TEXT,
  extraction_metadata_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### `chunks`

```sql
CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  extraction_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  token_count INTEGER,
  page_number INTEGER,
  heading TEXT,
  metadata_json TEXT
);
```

### `chunks_fts` (FTS5)

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
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
```

### `wiki_pages`

```sql
CREATE TABLE wiki_pages (
  id TEXT PRIMARY KEY,
  extraction_id TEXT,
  page_type TEXT NOT NULL,
  path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  sha256 TEXT,
  title TEXT,
  summary TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL
);
```

### `wiki_pages_fts` (FTS5)

```sql
CREATE VIRTUAL TABLE wiki_pages_fts USING fts5(
  wiki_page_id UNINDEXED,
  relative_path UNINDEXED,
  title,
  summary,
  content
);
```

### `proposed_updates`

```sql
CREATE TABLE proposed_updates (
  id TEXT PRIMARY KEY,
  wiki_page_id TEXT NOT NULL,
  source_file_id TEXT,
  source_relative_path TEXT,
  source_sha256 TEXT,
  target_relative_path TEXT,
  target_title TEXT,
  old_content TEXT NOT NULL,
  proposed_content TEXT NOT NULL,
  reason TEXT,
  confidence TEXT,
  source_citations_json TEXT,
  review_path TEXT,
  ingest_run_id TEXT,
  model TEXT,
  target_sha256_at_creation TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  edited_at TEXT,
  last_error TEXT,
  resolved_at TEXT
);
```

### `audit_events`

```sql
CREATE TABLE audit_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  target_path TEXT,
  source_paths_json TEXT,
  summary TEXT NOT NULL,
  details_json TEXT,
  created_at TEXT NOT NULL
);
```

### `flashcards`

```sql
CREATE TABLE flashcards (
  id TEXT PRIMARY KEY,
  extraction_id TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

### `review_items`

```sql
CREATE TABLE review_items (
  id TEXT PRIMARY KEY,
  extraction_id TEXT,
  title TEXT NOT NULL,
  issue TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
```

## Indexes

```sql
CREATE INDEX idx_files_vault_relative_path ON files(vault_id, relative_path);
CREATE INDEX idx_files_status ON files(processing_status);
CREATE INDEX idx_extractions_file ON extractions(file_id);
CREATE INDEX idx_chunks_extraction ON chunks(extraction_id);
CREATE INDEX idx_wiki_pages_relative_path ON wiki_pages(relative_path);
CREATE INDEX idx_proposed_updates_status ON proposed_updates(status);
CREATE INDEX idx_proposed_updates_source ON proposed_updates(source_relative_path);
```

## `files.processing_status` values in use

- `discovered`
- `queued`
- `processing`
- `processed`
- `skipped_unchanged`
- `pending_image`
- `extraction_limited`
- `unsupported`
- `failed_transient`
- `failed_permanent`
