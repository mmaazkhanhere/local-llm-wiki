# Database Schema

## MVP Tables

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

### `source_documents`

```sql
CREATE TABLE source_documents (
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
  source_document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  token_count INTEGER,
  page_number INTEGER,
  heading TEXT,
  metadata_json TEXT
);
```

### `generated_pages`

```sql
CREATE TABLE generated_pages (
  id TEXT PRIMARY KEY,
  source_document_id TEXT,
  page_type TEXT NOT NULL,
  path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  sha256 TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL
);
```

### `audit_log`

```sql
CREATE TABLE audit_log (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  target_path TEXT,
  source_paths_json TEXT,
  summary TEXT NOT NULL,
  details_json TEXT,
  created_at TEXT NOT NULL
);
```

## Deferred Tables

Not required for the first delivery slice:

- `qa_history`
- `flashcards`
- `active_recall_questions`

## Status Conventions

Recommended `files.processing_status` values:

- `discovered`
- `queued`
- `processing`
- `generated`
- `skipped_unchanged`
- `failed_transient`
- `failed_permanent`
