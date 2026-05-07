07/05/2026 12:51:37] AGENTS.md:56 Added required change logging format and rule.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/core/errors.py:13 Added explicit wiki-generation and LLM-output error types for fail-closed handling.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/llm/provider.py:7 Added the backend LLM provider interface used by structured Phase 3 generation.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/security/secrets.py:25 Added Groq key loading so wiki generation can reuse securely stored provider credentials.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/llm/groq.py:27 Added structured Groq completion support for wiki generation plans.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/db/service.py:14 Added file-level wiki generation tracking columns and migration guards.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/core/models.py:100 Extended ingest responses with wiki generation output summaries.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/ingestion/types.py:45 Extended ingest process summaries with wiki generation payloads.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/ingestion/service.py:215 Wired automatic wiki generation into full ingest runs and watcher-driven single-file processing.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/api/routes.py:181 Added wiki generation output to the queued-process and full-ingest API responses.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/wiki/models.py:30 Added validated Phase 3 candidate, flashcard, and generation-summary schemas.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/wiki/markdown.py:26 Added safe Markdown rendering, atomic writes, index updates, and log appends for generated wiki artifacts.
[07/05/2026 13:06:00] apps/desktop/backend/llm_wiki_backend/wiki/service.py:36 Added the Phase 3 wiki generation service that plans candidates and writes new wiki pages safely.
[07/05/2026 13:06:00] packages/shared/prompts/wiki_generation.md:4 Added the structured Phase 3 wiki-generation prompt contract.
[07/05/2026 13:06:00] apps/desktop/backend/tests/test_phase3.py:50 Added Phase 3 tests covering valid generation, invalid LLM output, and parser failures.
[07/05/2026 13:06:00] apps/desktop/electron/src/App.jsx:37 Added Raw Inbox UI state and tables for wiki generation candidate/output summaries.
[07/05/2026 13:14:00] apps/desktop/electron/electron/main.mjs:1 Added single-instance locking and PID/port handling so backend binds to port 8765 reliably and shuts down on app quit.
[07/05/2026 13:23:30] apps/desktop/backend/llm_wiki_backend/api/router/vault_router.py:1 Split vault endpoints into a dedicated APIRouter module.
[07/05/2026 13:23:30] apps/desktop/backend/llm_wiki_backend/api/router/provider_router.py:1 Split provider endpoints into a dedicated APIRouter module.
[07/05/2026 13:23:30] apps/desktop/backend/llm_wiki_backend/api/router/ingest_router.py:1 Split ingest endpoints into a dedicated APIRouter module.
[07/05/2026 13:23:30] apps/desktop/backend/llm_wiki_backend/api/router/__init__.py:1 Added combined api_router aggregator for main app wiring.
[07/05/2026 13:23:30] apps/desktop/backend/llm_wiki_backend/main.py:3 Updated backend app to include the aggregated api_router.
[07/05/2026 13:27:10] apps/desktop/backend/llm_wiki_backend/api/routes.py:1 Removed legacy routes module after migrating callers/tests to the new per-domain routers.
[07/05/2026 13:27:10] apps/desktop/backend/llm_wiki_backend/api/router/__init__.py:1 Avoided submodule name shadowing so tests can monkeypatch provider router symbols reliably.
[07/05/2026 13:27:10] apps/desktop/backend/tests/test_phase1.py:153 Updated provider monkeypatch targets to the new provider router module.
[07/05/2026 13:33:40] apps/desktop/electron/electron/main.mjs:1 Improved backend shutdown/startup reliability by awaiting shutdown on window close and killing any stale process holding port 8765.
[07/05/2026 13:38:20] apps/desktop/backend/llm_wiki_backend/api/router/vault_router.py:22 Added OpenAPI descriptions to Vault routes.
[07/05/2026 13:38:20] apps/desktop/backend/llm_wiki_backend/api/router/provider_router.py:17 Added OpenAPI descriptions to Provider routes.
[07/05/2026 13:38:20] apps/desktop/backend/llm_wiki_backend/api/router/ingest_router.py:20 Added OpenAPI descriptions to Ingest routes and restored `/ingest/raw/scan` path.
[07/05/2026 13:45:30] apps/desktop/backend/llm_wiki_backend/ingestion/service.py:1 Refactored ingestion service into smaller modules while preserving behavior and re-exporting PROTECTED_FOLDERS for watcher compatibility.
[07/05/2026 13:45:30] apps/desktop/backend/llm_wiki_backend/ingestion/repository.py:1 Extracted SQLite upsert and chunk persistence helpers from ingestion service.
[07/05/2026 13:45:30] apps/desktop/backend/llm_wiki_backend/ingestion/fs_utils.py:1 Extracted Raw/ scanning, protected path checks, and hashing helpers.
[07/05/2026 13:45:30] apps/desktop/backend/llm_wiki_backend/ingestion/time_utils.py:1 Centralized ingestion timestamp and token-count helpers.
[07/05/2026 16:11:50] apps/desktop/backend/llm_wiki_backend/observability/logging.py:1 Added colorama-based backend logging configuration and helpers.
[07/05/2026 16:11:50] apps/desktop/backend/llm_wiki_backend/main.py:1 Configured backend logging at startup.
[07/05/2026 16:11:50] apps/desktop/backend/llm_wiki_backend/ingestion/service.py:1 Added high-signal ingest lifecycle logs.
[07/05/2026 16:11:50] apps/desktop/electron/electron/main.mjs:1 Disabled Uvicorn access logs to avoid noisy repeated request lines caused by UI polling.
[07/05/2026 16:16:50] apps/desktop/backend/llm_wiki_backend/observability/events.py:1 Added an in-process event hub to broadcast backend events to WebSocket clients.
[07/05/2026 16:16:50] apps/desktop/backend/llm_wiki_backend/api/router/ws_router.py:1 Added FastAPI WebSocket endpoint for backend event streaming.
[07/05/2026 16:16:50] apps/desktop/backend/llm_wiki_backend/api/router/__init__.py:1 Included WebSocket router in the backend API.
[07/05/2026 16:16:50] apps/desktop/backend/llm_wiki_backend/ingestion/watcher.py:1 Published watcher events and added watcher logs.
[07/05/2026 16:16:50] apps/desktop/electron/src/App.jsx:37 Switched Raw Inbox updates to WebSocket-driven refresh with polling fallback.
[07/05/2026 16:16:50] apps/desktop/backend/llm_wiki_backend/observability/logging.py:1 Improved colored log formatting with subsystem tags for clearer output.
[07/05/2026 16:21:55] apps/desktop/electron/src/App.jsx:345 Fixed WebSocket fallback polling so it stops once the WS connection is open (prevents repeated inbox GETs).
[07/05/2026 16:21:55] apps/desktop/backend/llm_wiki_backend/observability/logging.py:46 Suppressed uvicorn access logs at the logger level as a second-line noise reduction.
