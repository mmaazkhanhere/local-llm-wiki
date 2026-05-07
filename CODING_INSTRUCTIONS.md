# LLM Wiki Coding Standard

Goal: clean, simple, production-ready code that is easy to change.

Stack:
- Desktop: Electron + React + Vite + TypeScript
- Backend: Python + FastAPI + Pydantic
- LLM: Groq behind `LLMProvider`
- Storage: SQLite + migrations + FTS5
- Files: Obsidian-compatible Markdown

## 1. Product Principle

Build a Karpathy-style compiled wiki:

Raw sources are immutable.
Wiki pages are generated, reviewed, cited, and audited.
Ask uses Wiki first, Raw second.
LLM output is never trusted until validated.

## 2. Architecture

Frontend:
- renders UI only
- calls typed API client only
- never reads/writes vault files directly
- never stores API keys

Electron:
- owns app window, tray, backend lifecycle, native dialogs
- exposes minimal IPC
- no business logic

Backend:
- owns vault validation, ingestion, retrieval, LLM calls, writes, audit logs
- FastAPI routes call services only
- domain logic is pure where possible

Database:
- SQLite for app state, jobs, sources, chunks, wiki index, audit events
- FTS5 before vector DB
- migrations required for schema changes

## 3. Project Shape

```text
apps/desktop/
  electron/
  renderer/
  api-client/

apps/backend/
  app/
    api/
    core/
    vault/
    ingestion/
    wiki/
    retrieval/
    llm/
    jobs/
    db/
    security/
    observability/
  tests/

packages/shared/
  prompts/
  schemas/
  markdown/
```

## 4. Dependency Rules
Allowed:

- api -> services
- services -> repositories/interfaces
- infrastructure -> domain models

Forbidden:
- React importing backend logic
- FastAPI routes containing business logic
- `core` importing FastAPI, Groq, Electron, Git, Obsidian, or real filesystem APIs
- direct Groq calls outside llm/
- direct vault writes outside vault/ or wiki/write_service.py


## 5. Safety Rules

Never:
- edit Raw/
- delete user files
- write outside Wiki/ and .llm-wiki/
- log API keys
- let LLM choose paths unchecked
- overwrite existing pages without review

Always:
- normalize and validate paths
- use atomic writes
- record every write in audit log
- show diff before updating an existing page
- keep raw source citations for generated claims
- reject unsafe LLM output

## 6. Backend Rules

Python:
- type hints everywhere
- Pydantic models for API and LLM structured outputs
- explicit exceptions for expected failures
- graceful error handling and retry logics
- pathlib.Path for paths
- no hidden I/O in pure logic
- AWLAYS split files around 250–350 lines when responsibilities diverge
- a `config.py` file that will hold all the application wide constants and configurations
- complete logging system in the backend that gives complete observability of the operations happening. Use colorama for different log levels

Service pattern:
```text
plan -> validate -> diff -> approve -> atomic write -> audit -> reindex
```

## 7. Frontend Rules

React:
- small resuable components
- server state via TanStack Query or equivalent
- local UI state only in components/hooks
- typed API client generated from OpenAPI
- clear loading, empty, error, review, and success states

Screens:
- Dashboard
- Raw Inbox
- Ingestion Jobs
- Proposed Updates
- Wiki Browser
- Ask
- Lint
- Settings

Electron:
- minimal IPC
- no filesystem mutation from renderer
- backend health check on startup
- graceful backend shutdown when the frontend is closed

## 8. LLM Rules

All LLM calls go through:
``` python
class LLMProvider:
    def complete_structured(...)
    def stream(...)
```
Rules:
- model IDs live in config
- prompts are versioned
- outputs are schema-validated
- invalid outputs fail closed
- citations are required where source-backed claims exist
- retries are bounded
- streaming is optional, not architectural

## 9. Jobs

Long work must be a job:
- ingest source
- extract text
- chunk/index
- plan wiki update
- generate page
- lint wiki
- rebuild search index

Each job has:

- id
- status
- progress
- logs
- error
- created_at
- finished_at
- cancel support where safe

## 10. Retrieval

Default order:
- Wiki FTS
- Wiki backlinks/index pages
- Raw chunk FTS for verification
- LLM synthesis with citations

Rules:
- Wiki is primary
- Raw is evidence
- no answer without provenance when sources exist
- store retrieval traces for debugging

## 11. Testing
- Use TDD approach for coding
- Write tests before implementation
- Use pytest for backend tests.

Required tests depending on the feature implementation:
### 1. Vault Safety

- rejects paths outside vault
- rejects writes to `Raw/`
- allows writes only to `Wiki/` and `.llm-wiki/`
- requires approval before updating existing wiki pages
- never allows delete operations

### 2. Wiki Page Logic

- creates safe filename from title
- rejects unsafe LLM-proposed paths
- creates page plan for new page
- creates diff plan for existing page
- rejects uncited claims when sources are available

### 3. LLM Output Validation

- accepts valid structured output
- rejects invalid JSON
- rejects missing required fields
- rejects unsafe target path
- rejects output that violates citation rules

### 4. Ingestion Logic

- detects duplicate files by hash
- detects changed file with same name
- chunks text under max size
- preserves source id and chunk order
- ignores generated `Wiki/` files as raw sources

### 5. Retrieval / Ask Logic

- ranks Wiki results before Raw results
- uses Raw only as supporting evidence
- removes duplicate results
- keeps context under budget
- returns citations with selected context

### 6. Audit Logic

- creates audit event for every write plan
- includes action, path, timestamp, actor, and hash
- redacts secrets from audit/log output
- rejects write plan without audit event

### 7. Job State Logic

- supports `queued -> running -> succeeded`
- supports `running -> failed`
- supports `running -> cancelled`
- rejects invalid state transitions
- keeps progress between `0` and `100`

### Non Unit tests
- actual atomic file replacement
- real SQLite FTS5 ranking
- real migration execution
- real Markdown write/read
- real PDF/text extraction
- FastAPI route behavior
- Electron app startup


### 8. Frontend Logic

- shows loading, error, empty, and success states
- disables approve/reject while request is pending
- displays diff before approval
- never calls filesystem APIs directly
- never displays full API key


## 12. Definition of Done
A change is done only when:
- one feature only
- tests added first or alongside code
- unit/integration tests pass
- type checks pass
- lint passes
- no unrelated refactor
- no new global state
- no direct unsafe file writes
- no direct Groq calls outside provider
- docs updated if behavior changed

## 13. Security Rules

- Do not log secrets (API keys, tokens, etc.).
- Do not store secrets in plaintext in the codebase.
- Use environment variables for sensitive configuration.
- Encrypt sensitive data at rest when applicable.
- Implement proper input validation to prevent injection attacks.
- Use prepared statements or ORMs for database operations.

## 14. Error Handling

- Use explicit exception types instead of generic Exception.
- Never swallow exceptions without logging or handling them.
- Provide meaningful error messages to the user.
- Use proper retry logic with exponential backoff for network operations.
- Handle gracefully the cases when the LLM is not available, providing the user with alternative options
