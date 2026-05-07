[07/05/2026 12:51:37] AGENTS.md:56 Added required change logging format and rule.
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
