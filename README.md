# Local LLM Wiki

Phase 0 delivers a runnable desktop shell:

- Electron desktop app
- React renderer with basic navigation placeholders
- Python FastAPI backend
- Electron starts/stops backend automatically
- Frontend health check against backend

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

## Phase 0 Acceptance Mapping

- Desktop app launches: `apps/desktop/electron` dev script
- Python backend launches from Electron: Electron main process spawns backend
- Frontend can call backend health check: renderer polls `/health` via preload bridge
- Basic navigation exists: Dashboard, Raw Inbox, Proposed Updates, Wiki Browser, Ask, Lint, Settings
- Tests pass: backend test suite
- Project runnable by README instructions: commands above
