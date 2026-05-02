# Simple Wiki Coding & Architecture Instructions

Write clean, boring, test-driven code. Optimize for correctness, safety, readability, and easy change. Build one feature at a time.

---

## 1. Core Rules

- Implement one feature per change.
- Start every feature with a small test list.
- Use TDD: red → green → refactor.
- Keep functions small and names explicit.
- Prefer simple data flow over clever abstractions.
- Do not add architecture for hypothetical future needs.
- Keep business logic separate from UI, APIs, filesystem, LLM providers, Git, and Obsidian CLI.
- Treat LLM output as untrusted until validated.

---

## 2. Project Safety Rules

The app manages a user’s Obsidian vault. Safety is mandatory.

- Never edit `Raw/`.
- Never delete user files.
- Never write outside `Wiki/` and `.llm-wiki/`.
- Use atomic writes for Markdown files.
- New wiki pages may be created automatically.
- Updates to existing wiki pages require review/approval.
- Every write must be recorded in the audit log.
- API keys must be stored securely and never logged.
- Raw source chunks are for verification/citation, not primary reasoning.
- Ask must use compiled wiki pages first, raw sources second.

---

## 3. Architecture Boundaries

Use clear layers. Keep domain logic independent from infrastructure.

```text
apps/desktop/
  electron/        React + Electron UI
  backend/         Python FastAPI backend

packages/shared/
  prompts/         shared prompt text
  schema/          shared JSON schemas
  markdown/        shared Markdown templates
```

Backend module boundaries:

```text
core/              pure workflow decisions
api/               FastAPI routes only
vault/             vault validation and path rules
ingestion/         file extraction and chunking
wiki/              page planning, links, index, log, writes
retrieval/         SQLite FTS5 search and ranking
llm/               provider interface and Groq adapter
lint/              wiki health checks and safe auto-fixes
db/                SQLite repositories and migrations
git/               optional Git adapter
obsidian/          optional Obsidian CLI adapter
security/          keychain and secret handling
```

Rules:

- `api/` should call services, not contain business logic.
- `core/` should not import FastAPI, Electron, Groq, Git, Obsidian CLI, or real filesystem APIs.
- Infrastructure should sit behind small interfaces.
- Prefer dependency injection over globals.
- Keep side effects at the edges.

---

## 4. TDD Workflow

For every feature:

1. Write the test list.
2. Write one failing test.
3. Implement the smallest code that passes.
4. Refactor while tests stay green.
5. Repeat until the feature is complete.

Example test list:

```text
Feature: Create vault folders
- creates Raw/, Wiki/, and .llm-wiki/
- does not overwrite existing index.md
- rejects non-directory vault path
- writes nothing outside the vault
```

A feature is done only when:

- tests cover normal and edge cases,
- lint/type checks pass,
- code is refactored,
- behavior is small and reviewable.

---

## 5. Testing Rules

Use many fast unit tests, fewer integration tests, and very few end-to-end tests.

```text
Unit tests:
  Pure logic, no network, no real Groq, no real Obsidian vault.

Integration tests:
  SQLite, temp directories, Markdown writes, parsers.

End-to-end tests:
  Critical flows only.
```

Required test areas:

- vault path validation
- Raw/Wiki write boundaries
- hash-based file detection
- file extraction
- SQLite FTS5 indexing
- wiki page creation
- proposed update diffs
- audit logging
- citation formatting
- lint checks
- Ask retrieval order
- Groq adapter with mocked responses

Never call real Groq, real Obsidian CLI, or real user vaults in tests.

---

## 6. Python Backend Rules

- Use type hints everywhere.
- Use Pydantic models for API and structured LLM outputs.
- Keep functions short and single-purpose.
- Avoid hidden I/O in domain functions.
- Use `pathlib.Path` for paths.
- Validate every path stays inside the selected vault.
- Use explicit exceptions for expected failures.
- Keep prompts versioned and testable.
- Parse and validate LLM responses before writing files.
- Split a Python file when it starts doing more than one clear responsibility or becomes hard to navigate, test, or reuse.
- If your Python file is getting long (e.g. > 500–700 lines), split it.

Good pattern:

```text
plan update → validate update → show diff → approve → atomic write → audit
```

Bad pattern:

```text
LLM response → directly overwrite Markdown
```

---

## 7. React/Electron Rules

- Keep UI components small.
- Keep business logic in the backend, not React.
- Use typed API clients.
- Show clear loading, error, pending, and review states.
- Never let the frontend write directly to the vault.
- Diff review must be explicit and easy to understand.
- Prefer simple screens over dense dashboards.

Main UI areas:

```text
Dashboard
Raw Inbox
Proposed Updates
Wiki Browser
Ask
Lint
Settings
```

---

## 8. LLM Coding Rules

- LLM calls must go through `LLMProvider`.
- Do not hardcode Groq throughout the codebase.
- Keep model IDs in config.
- Validate structured outputs with schemas.
- Reject outputs that violate path, citation, or page-type rules.
- Never trust the LLM to choose write paths without validation.
- All generated claims should cite raw sources when practical.

---

## 9. SQLite Rules

- Use migrations.
- Keep writes transactional.
- Use FTS5 for wiki and raw chunk search.
- Wiki search is primary.
- Raw chunk search is secondary for verification.
- Do not store secrets in SQLite.
- Do not require committing `app.db` to Git.

---

## 10. Commit Discipline

Each commit should represent one concept.

Good commits:

```text
feat(vault): create required folders
feat(ingestion): extract text from pdf files
feat(wiki): create concept page from ingest plan
test(retrieval): verify wiki-first ask ranking
```

Avoid commits that mix unrelated features, refactors, UI polish, and bug fixes.

Before merging:

```text
- tests pass
- type checks pass
- lint passes
- no real secrets in logs/config
- no writes outside allowed folders
- no unrelated refactors
```

---

## 11. Anti-Patterns

Do not:

- build a plugin system early,
- add vector DB before SQLite FTS5 is proven insufficient,
- make the frontend responsible for core logic,
- let LLM output directly modify files,
- mix ingestion, retrieval, UI, and Git in one module,
- create huge concept pages,
- write uncited claims when a source is available,
- process generated `Wiki/` files as raw sources,
- test against real user data.

---

## 12. Implementation Style

Default to the simplest working design:

```text
small feature
small test list
small failing test
small implementation
small refactor
small commit
```

The codebase should feel easy for a senior engineer to review and safe for an AI coding agent to modify.
