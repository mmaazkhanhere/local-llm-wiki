# Local LLM Wiki

Current implementation includes Phase 0, Phase 1, and Phase 2 foundations:

- Electron desktop app
- React renderer with basic navigation placeholders
- Python FastAPI backend
- Electron starts/stops backend automatically
- Frontend health check against backend
- Vault bootstrap (`Raw/`, `Wiki/`, `.llm-wiki/`, `index.md`, `log.md`, `app.db`, `config.json`)
- Raw ingest pipeline: scan, hash, watch, extract, and FTS5 chunk indexing

## Repository Layout

```text
apps/
  desktop/
    electron/
    backend/
  android/
packages/
  shared/
    prompts/
    schema/
tests/
docs/
```

## Prerequisites

- Node.js 20+
- npm 10+
- Python 3.11+
- `uv` installed and available in `PATH`

## Run Backend Tests

```powershell
cd apps/desktop/backend
uv sync --extra dev
uv run pytest -q
```

## Run Desktop App (Phase 0)

```powershell
cd E:\Web 3.0\Generative AI\Github\local-llm-wiki
npm install
npm run desktop:dev
```

What this starts:

1. Vite dev server for React UI
2. Electron app window
3. Python backend process launched by Electron (`uv run uvicorn ...`)

## Phase 2 Acceptance Mapping

- App scans `Raw/`: `/ingest/raw/scan` and `/ingest/raw/run`
- App watches `Raw/`: `/ingest/raw/watch/start|stop|status`
- Protected folders ignored: scan/watcher exclude `Wiki/`, `.llm-wiki/`, `.obsidian/`, `.git/`, `.trash/`
- Hash-based reprocessing: `/ingest/raw/hash` and DB `files.sha256`
- Extraction coverage: `.md`, `.txt`, `.pdf`, `.docx`, `.html/.htm`, code and structured text
- Images marked pending: `processing_status = pending_image`
- Chunks in SQLite FTS5: `chunks_fts` table
- Raw files are read-only during ingest
- Tests pass: `uv run pytest -q`
