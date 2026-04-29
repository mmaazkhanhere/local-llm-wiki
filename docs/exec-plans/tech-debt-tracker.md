# Tech Debt Tracker

## Open Debt

### TD-001 Embeddings Deferred

Reason:

- not required for first-pass Q&A

Future trigger:

- lexical retrieval quality becomes inadequate on larger vaults

### TD-002 Richer File Type Coverage

Reason:

- PDF, DOCX, HTML, and image ingestion increase parser and reliability surface

Future trigger:

- markdown/text path is stable

### TD-003 Git UX Hardening

Reason:

- generated-only staging must be airtight before enabling by default

### TD-004 Repair Tools

Reason:

- auto-write flow benefits from index/audit repair commands after partial failures
