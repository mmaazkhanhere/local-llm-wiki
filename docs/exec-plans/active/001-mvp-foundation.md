# 001 MVP Foundation

## Objective

Ship the safety-first MVP foundation for a local desktop Obsidian wiki generator.

## Scope

- desktop shell
- vault setup
- watcher exclusions
- database schema
- markdown/text ingestion
- provider abstraction
- summary generation
- auto-write path
- audit logging
- basic dashboard and activity visibility

## Tickets

### MVP-001 Repository Skeleton

Deliver:

- Python package skeleton
- app entrypoint
- config loading

Acceptance criteria:

- app launches
- config file can be created and loaded

### MVP-002 Vault Setup and Folder Ownership

Deliver:

- vault picker
- folder creation for `LLM Wiki/` and `.llm-wiki/`
- path ownership guard

Acceptance criteria:

- required folders are created once
- writes outside app-owned folders are rejected

### MVP-003 Watcher Exclusions and Scan

Deliver:

- initial vault scan
- exclusion rules for app-owned and metadata folders
- supported-extension filtering

Acceptance criteria:

- `LLM Wiki/`, `.llm-wiki/`, `.obsidian/`, `.git/`, `.trash/` are excluded
- unchanged generated files do not re-enter ingestion

### MVP-004 SQLite Schema and Status Tracking

Deliver:

- `vaults`
- `files`
- `source_documents`
- `chunks`
- `generated_pages`
- `audit_log`

Acceptance criteria:

- schema initializes on first run
- file status transitions are persisted

### MVP-005 Hashing and Idempotency

Deliver:

- SHA-256 hashing
- unchanged-file no-op behavior
- collision-safe generated filename resolution

Acceptance criteria:

- unchanged files are skipped
- repeated watcher events do not duplicate outputs

### MVP-006 Markdown and Text Ingestion

Deliver:

- `.md` and `.txt` extraction
- title extraction
- chunking

Acceptance criteria:

- extracted text stored in DB
- chunks stored with index order

### MVP-007 Provider Abstraction and Groq Integration

Deliver:

- `base.py` interface
- Groq implementation
- provider key validation

Acceptance criteria:

- summary generation works through interface only
- model name comes from config, not hardcoded call sites

### MVP-008 Summary Template and Auto-Write

Deliver:

- source summary prompt
- markdown template
- atomic file writer

Acceptance criteria:

- generated summary lands in `LLM Wiki/Sources/`
- raw notes are untouched

### MVP-009 Index, Processing Log, and Audit Log

Deliver:

- `_Index.md` updates
- `_Processing Log.md` updates
- `LLM Wiki/Audit/audit-log.jsonl`

Acceptance criteria:

- each successful summary write is reflected in all three places

### MVP-010 Dashboard and Activity UI

Deliver:

- processed counts
- queued or processing counts
- recent files
- recent errors

Acceptance criteria:

- user can see what was generated and what failed

### MVP-011 Ask MVP with Simple Text Retrieval

Deliver:

- lexical retrieval over summaries and chunks
- grounded answer generation

Acceptance criteria:

- embeddings are not required
- unsupported answers are stated explicitly

### REL-001 Retry and Error Taxonomy

Deliver:

- transient vs permanent error types
- bounded retry helper
- file status mapping

Acceptance criteria:

- provider, parser, and locked-file retries behave per `RELIABILITY.md`

### REL-002 Atomic Write and Repair Path

Deliver:

- temp-file write then rename
- inconsistent-write detection
- repair-needed status

Acceptance criteria:

- partial writes are not left behind as final outputs

### SEC-001 Credential and Path Safety

Deliver:

- keyring integration
- normalized output path validation

Acceptance criteria:

- keys are not stored in plaintext unless fallback is explicitly chosen
- unsafe output paths are rejected

## Dependencies

- `MVP-002` depends on `MVP-001`
- `MVP-003` depends on `MVP-002`
- `MVP-004` depends on `MVP-001`
- `MVP-005` depends on `MVP-003` and `MVP-004`
- `MVP-006` depends on `MVP-004`
- `MVP-007` depends on `MVP-001`
- `MVP-008` depends on `MVP-006` and `MVP-007`
- `MVP-009` depends on `MVP-008`
- `MVP-010` depends on `MVP-003`, `MVP-004`, and `MVP-009`
- `MVP-011` depends on `MVP-006`, `MVP-007`, and `MVP-009`

## Exit Criteria

This plan is complete when:

- markdown/text sources can be processed end to end
- summaries auto-write safely
- audit and index files update correctly
- failures are visible and bounded
