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
[07/05/2026 17:05:00] packages/shared/prompts/wiki_generation.md:1 Updated wiki generation prompts for conciseness, source-grounding, and strict JSON validation.
[07/05/2026 18:53:38] apps/desktop/backend/tests/test_phase4.py:36 Added phase 4 backend coverage for proposal creation, editing, approval, rejection, conflict handling, and approve-all behavior.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/wiki/models.py:42 Added structured proposal/update review models and phase-4 summary fields.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/db/service.py:7 Expanded SQLite schema and migration helpers for review proposals, wiki FTS, and proposal metadata.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/wiki/markdown.py:57 Added review-file rendering plus markdown title/summary extraction helpers for approved updates.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/observability/audit.py:16 Added durable audit recording to SQLite and `.llm-wiki/audit.jsonl`.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:29 Implemented FTS-backed related-page lookup, proposal persistence, diff building, approval/rejection flows, conflict detection, and index/log follow-up writes.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/wiki/service.py:39 Integrated phase-4 proposal generation into wiki ingest while preserving new-page generation.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/core/models.py:122 Added API models for proposal listing, editing, and approve-all responses.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/api/router/review_router.py:23 Added review API routes for listing, loading, editing, approving, rejecting, and bulk-approving proposals.
[07/05/2026 18:53:38] apps/desktop/backend/llm_wiki_backend/api/router/__init__.py:7 Registered the review router with the backend API.
[07/05/2026 18:53:38] apps/desktop/electron/electron/preload.mjs:18 Exposed review workflow IPC methods to the renderer.
[07/05/2026 18:53:38] apps/desktop/electron/electron/main.mjs:344 Added Electron-side review API bridge handlers and PUT request support.
[07/05/2026 18:53:38] apps/desktop/electron/src/App.jsx:15 Replaced the Proposed Updates placeholder with a working review queue, diff viewer, editor, and approve/reject actions.
[07/05/2026 18:53:38] apps/desktop/electron/src/styles.css:69 Added layout and diff/editor styling for the Proposed Updates workflow.
[07/05/2026 18:53:38] docs/product-specs/review-workflow.md:1 Added the canonical product spec for existing-page review proposals.
[07/05/2026 18:53:38] docs/product-specs/index.md:7 Registered the new review workflow spec in the product-spec read order.
[07/05/2026 18:53:38] docs/product-specs/file-processing.md:17 Updated file-processing behavior to distinguish direct new-page writes from review-gated existing-page updates.
[07/05/2026 18:53:38] docs/design-docs/auto-write-safety.md:3 Updated the safety design note to reflect review-gated existing-page updates.
[07/05/2026 18:53:38] docs/generated/db-schema.md:83 Regenerated the schema reference for wiki page FTS and expanded proposal metadata.
[07/05/2026 21:30:07] apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:323 Fixed approval conflict handling for legacy proposals by backfilling `target_sha256_at_creation` from stored old content.
[07/05/2026 21:45:51] apps/desktop/electron/src/App.jsx:321 Reworked Proposed Updates list to focus on target wiki pages and applied optimistic UI updates so approve/reject remove proposals immediately.
[07/05/2026 21:56:27] apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:333 Removed app-owned `Wiki/Reviews/*` files on approve/reject and audited the removal to prevent stale review artifacts.
[07/05/2026 21:56:27] apps/desktop/electron/src/App.jsx:441 Forced a post-action refresh after save/edit/approve/reject so resolved proposals cannot reappear when new proposals arrive.
[07/05/2026 22:02:25] apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:396 Made proposal approval validate markdown title/summary before writing to prevent partial writes when proposed content is invalid.
[07/05/2026 22:02:25] apps/desktop/backend/tests/test_phase4.py:290 Added regression test ensuring invalid proposed content fails closed and does not modify the target page.
[07/05/2026 22:07:33] apps/desktop/electron/src/App.jsx:446 Fixed approve UI handling for validation-failed proposals (status stays pending) and surfaced `last_error` in list/detail to explain why changes weren’t applied.
08/05/2026 11:43:03 docs/product-specs/review-workflow.md:9 Updated review workflow to gate new page creation on absence of related existing pages.
08/05/2026 11:43:03 apps/desktop/backend/llm_wiki_backend/wiki/service.py:122 Prefer update proposals over new page creation when related pages are found.
08/05/2026 11:48:44 packages/shared/prompts/wiki_coverage_check.md:1 Added LLM coverage-check prompt to gate new page creation.
08/05/2026 11:48:44 apps/desktop/backend/llm_wiki_backend/wiki/models.py:79 Added schema for LLM wiki coverage decision.
08/05/2026 11:48:44 apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:28 Added exact title match retrieval for existing pages.
08/05/2026 11:48:44 apps/desktop/backend/llm_wiki_backend/wiki/service.py:110 Added 3-stage coverage gating with ranked candidates before new page creation.
08/05/2026 11:48:44 docs/product-specs/review-workflow.md:9 Documented ranked coverage check + gating behavior.
08/05/2026 12:20:07 apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:22 Tightened update prompt + fail-closed validation to avoid overwriting unrelated pages.
08/05/2026 12:20:07 apps/desktop/backend/llm_wiki_backend/wiki/models.py:64 Added target_path to update plan schema for precise matching.
[11/05/2026 10:59:22] App.jsx:42 Added proposal draft tracking state and guarded refresh logic so polling/events do not overwrite unsaved proposal edits in the Proposed Updates editor.
[11/05/2026 10:59:22] App.jsx:427 Updated review actions to support discard, auto-save edited proposal content before approve, and block proposal switching while unsaved edits exist.
[11/05/2026 10:59:22] styles.css:237 Added editor header and saved/unsaved draft badge styles to make proposal edit state clear in the review UI.
[11/05/2026 12:05:00] IMPLEMENTATION_PHASES.md:853 Added a sequential Phase 5 Ask implementation plan with per-feature testing and verification gates aligned to the implementation plan.
[11/05/2026 12:05:00] change-log.md:86 Logged the Phase 5 Ask planning update.
[11/05/2026 12:45:00] apps/desktop/backend/llm_wiki_backend/core/models.py:155 Added Ask request/response/propose models for Ask API contracts.
[11/05/2026 12:45:00] apps/desktop/backend/llm_wiki_backend/ask/service.py:35 Added Ask service pipeline with wiki-first retrieval, neighbor expansion, optional raw verification, citation validation, and proposal creation.
[11/05/2026 12:45:00] apps/desktop/backend/llm_wiki_backend/api/router/ask_router.py:11 Added Ask routes for query and proposal handoff with vault validation and fail-closed error handling.
[11/05/2026 12:45:00] apps/desktop/backend/llm_wiki_backend/api/router/__init__.py:17 Wired Ask router into the backend API.
[11/05/2026 12:45:00] apps/desktop/backend/llm_wiki_backend/ask/__init__.py:1 Added Ask package marker module.
[11/05/2026 12:45:00] apps/desktop/electron/electron/main.mjs:427 Added Electron IPC handlers for Ask query and Ask-to-proposal actions.
[11/05/2026 12:45:00] apps/desktop/electron/electron/preload.mjs:26 Exposed Ask IPC methods on the renderer bridge.
[11/05/2026 12:45:00] apps/desktop/electron/src/global.d.ts:65 Added Ask bridge typings for query and proposal responses.
[11/05/2026 12:45:00] apps/desktop/electron/src/App.jsx:552 Implemented Ask UI flow with question submission, answer/citation display, unsupported handling, and Propose Wiki Update action.
[11/05/2026 12:45:00] apps/desktop/electron/src/styles.css:281 Added Ask-specific input/result styling for readable answer and citation presentation.
[11/05/2026 12:45:00] apps/desktop/backend/tests/test_phase5.py:83 Added Phase 5 tests for wiki-first retrieval, raw fallback, citation hallucination rejection, and reviewable Ask proposal creation.
[11/05/2026 12:45:00] change-log.md:98 Logged Phase 5 Ask implementation updates.
[11/05/2026 12:53:00] apps/desktop/backend/llm_wiki_backend/ask/service.py:49 Tightened raw fallback so Ask uses raw chunks only when no wiki evidence is found.
[11/05/2026 12:53:00] change-log.md:100 Logged Ask retrieval fallback correction and local Phase 5 test pass verification.
[11/05/2026 18:32:29] apps/desktop/backend/llm_wiki_backend/db/service.py:1 Add Phase 6 lint tables (lint_runs, lint_issues) and indexes during DB init.
[11/05/2026 18:32:29] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Add minimal post-ingest lint runner + latest status query (Phase 6.1 scaffold).
[11/05/2026 18:32:29] apps/desktop/backend/llm_wiki_backend/wiki/service.py:1 Allow callers to supply ingest_run_id so downstream lint/audit can link runs.
[11/05/2026 18:32:29] apps/desktop/backend/llm_wiki_backend/ingestion/service.py:1 Generate ingest_run_id per ingest and trigger post-ingest lint; return lint summary.
[11/05/2026 18:32:29] apps/desktop/backend/llm_wiki_backend/api/router/lint_router.py:1 Add lint API endpoints (/lint/latest, /lint/run).
[11/05/2026 18:32:29] apps/desktop/backend/llm_wiki_backend/api/router/ingest_router.py:1 Ensure lint runs after manual /raw/process path and returns ingest_run_id + lint summary.
[11/05/2026 18:32:29] apps/desktop/backend/tests/test_phase6.py:1 Add Phase 6.1 tests for lint auto-run after ingest and latest lint endpoint.
[11/05/2026 18:32:29] docs/generated/db-schema.md:1 Document lint tables and indexes in generated schema mirror.
[11/05/2026 18:35:59] apps/desktop/backend/llm_wiki_backend/wiki/service.py:153 Gate coverage-check LLM call to real Groq provider to keep test fakes deterministic and avoid extra unexpected LLM calls.
[11/05/2026 18:38:25] apps/desktop/backend/llm_wiki_backend/wiki/models.py:78 Relax update-plan schema: allow missing target_path and resolve proposals by title when needed.
[11/05/2026 18:38:25] apps/desktop/backend/llm_wiki_backend/wiki/review_service.py:203 Match proposed update items by target_title when LLM omits target_path (keeps workflow robust and tests deterministic).
[11/05/2026 18:40:29] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Implement Phase 6.2 deterministic mechanical lint checks (broken links, missing index entries, duplicates, empties) and persist issues to SQLite.
[11/05/2026 18:40:29] apps/desktop/backend/tests/test_phase6.py:1 Add Phase 6.2 tests covering mechanical lint issue persistence for broken links + missing index entry.
[11/05/2026 18:42:56] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Expand mechanical lint to include broken raw source references, invalid frontmatter fences, and missing log entries.
[11/05/2026 18:42:56] apps/desktop/backend/tests/test_phase6.py:1 Add mechanical lint test for broken raw source reference + invalid frontmatter detection.
[11/05/2026 18:44:15] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Add Phase 6.3 provenance lint to flag wiki pages missing Raw-backed Source references.
[11/05/2026 18:44:15] apps/desktop/backend/tests/test_phase6.py:1 Add provenance lint test ensuring missing sources are recorded as lint issues.
[11/05/2026 18:46:39] apps/desktop/backend/llm_wiki_backend/db/service.py:1 Add `lint_fixes` table to persist safe fix diffs/results.
[11/05/2026 18:46:39] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Implement Phase 6.4 safe mechanical auto-fixes with dry-run support and audit events for applied writes.
[11/05/2026 18:46:39] apps/desktop/backend/llm_wiki_backend/api/router/lint_router.py:1 Add `/lint/fix/apply` endpoint to run safe auto-fixes for a lint run.
[11/05/2026 18:46:39] apps/desktop/backend/tests/test_phase6.py:1 Add test covering dry-run vs apply behavior for missing index entry auto-fix.
[11/05/2026 18:46:39] docs/generated/db-schema.md:1 Document `lint_fixes` table and index in schema mirror.
[11/05/2026 18:48:59] packages/shared/prompts/lint_semantic.md:1 Add semantic lint system prompt template for Phase 6.5.
[11/05/2026 18:48:59] apps/desktop/backend/llm_wiki_backend/lint/models.py:1 Add Pydantic schema for semantic lint results to validate LLM output.
[11/05/2026 18:48:59] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Add semantic lint runner that stores issues only (no edits) and upgrades status to needs_review when semantic issues exist.
[11/05/2026 18:48:59] apps/desktop/backend/llm_wiki_backend/api/router/lint_router.py:1 Add `semantic` option on `/lint/run` to trigger semantic lint pass.
[11/05/2026 18:48:59] apps/desktop/backend/tests/test_phase6.py:1 Add semantic lint test using mocked provider and verifying issues persisted to SQLite.
[11/05/2026 18:51:06] apps/desktop/backend/llm_wiki_backend/db/service.py:1 Add `review_pages` table + indexes to persist semantic review artifacts.
[11/05/2026 18:51:06] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Add Phase 6.6 semantic review page generator writing to `Wiki/Reviews/` with fingerprint-based dedupe.
[11/05/2026 18:51:06] apps/desktop/backend/llm_wiki_backend/api/router/lint_router.py:1 Add `/lint/reviews/create` endpoint to materialize semantic issues as review pages.
[11/05/2026 18:51:06] apps/desktop/backend/tests/test_phase6.py:1 Add test verifying semantic review page creation + duplicate avoidance.
[11/05/2026 18:51:06] docs/generated/db-schema.md:1 Document `review_pages` table and indexes in schema mirror.
[11/05/2026 18:54:33] apps/desktop/electron/electron/main.mjs:1 Add Electron IPC handlers for lint status/run/fixes/review page creation endpoints.
[11/05/2026 18:54:33] apps/desktop/electron/electron/preload.mjs:1 Expose lint API functions to renderer via window.desktopApi.
[11/05/2026 18:54:33] apps/desktop/electron/src/global.d.ts:1 Extend desktopApi typings with lint functions.
[11/05/2026 18:54:33] apps/desktop/electron/src/App.jsx:1 Add Lint view UI + dashboard lint summary, and wire lint actions through Electron bridge.
[11/05/2026 18:57:39] apps/desktop/backend/llm_wiki_backend/lint/service.py:1 Append Phase 6 lint summary sections to `Wiki/log.md`, audit log appends, and keep lint_runs counters in sync when semantic lint/fixes/review pages are applied.
[11/05/2026 18:57:39] apps/desktop/backend/llm_wiki_backend/api/router/lint_router.py:1 Return refreshed lint run summary after optional semantic lint so UI reflects updated counters/status.
[11/05/2026 22:46:37] apps/desktop/electron/src/App.jsx:5 Rename Lint nav tab label to "Content Review" while keeping internal view key unchanged.
[11/05/2026 22:48:42] apps/desktop/electron/src/App.jsx:1146 Rename semantic lint CTA button to "Review Content using AI" for clearer UX.
[11/05/2026 22:50:47] apps/desktop/electron/src/App.jsx:1163 Rename safe-fix buttons to "Fix Content" and "Apply Fixes" for clearer UX.
