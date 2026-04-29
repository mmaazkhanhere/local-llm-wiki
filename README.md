## Local LLM Wiki

GUI-first desktop app for local Obsidian vault processing.

Implemented:

- `MVP-001` package skeleton, app entrypoint, config load/save
- `MVP-002` vault setup and app-owned write-path guard
- `MVP-003` vault scan with exclusions and supported-extension filtering
- `MVP-004` SQLite schema initialization and persisted file status transitions
- `MVP-005` SHA-256 idempotency behavior (`skipped_unchanged` on unchanged scans)
- `MVP-006` `.md`/`.txt` extraction, title extraction, chunking, and persistence
- `MVP-007` provider abstraction and Groq provider implementation
- `MVP-008` source summary prompt, Markdown template, and atomic summary file write
- `MVP-009` `_Index.md`, `_Processing Log.md`, and JSONL/SQLite audit logging on successful writes
- `MVP-010` dashboard and activity visibility for counts, recent generated files, and recent errors
- `MVP-011` Ask MVP with lexical retrieval over summaries/chunks and grounded citation output

### Launch GUI

```bash
uv run python -m llm_wiki.gui_app
```

### Packaged app

- GUI executable is built at:
  - `dist\local-llm-wiki.exe`

### Run tests

```bash
uv run pytest -q
```
