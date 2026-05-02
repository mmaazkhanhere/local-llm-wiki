# Implementation Phases
## Global development rule

Each phase must be implemented as a sequence of small features.

For every feature:

```text
1. Define the expected behavior.
2. Write or update tests first.
3. Implement the smallest working version.
4. Refactor only after tests pass.
5. Update docs if behavior changed.
6. Commit the feature.
7. Move to the next feature only when the current one is complete.
```

Do not work on multiple major features at once. Do not start the next phase until the current phase meets its acceptance criteria.

---

# Phase 0 — Repo and skeleton

## Goal
Create the minimum working app shell: Electron + React frontend, Python FastAPI backend, and a working connection between them.
## Feature 0.1 — Create monorepo
Create the base repository structure:

```text
simple-wiki/
  apps/
    desktop/
      electron/
      backend/
    android/
  packages/
    shared/
      prompts/
      schema/
  docs/
  tests/
```

### Complete when
* Repo structure exists.
* `README.md` explains the project.
* `docs/` contains the product plan and coding instructions.
* Root scripts are documented.
* Empty app folders are intentionally structured for desktop first and Android later.

---

## Feature 0.2 — Create Electron + React app
Create the desktop frontend shell.
### Complete when
* Electron app starts successfully.
* React UI renders.
* App has a basic window title and layout.
* App has placeholder navigation for:
  * Dashboard
  * Raw Inbox
  * Proposed Updates
  * Wiki Browser
  * Ask
  * Lint
  * Settings

---

## Feature 0.3 — Create Python FastAPI backend
Create a minimal backend service.
### Complete when
* FastAPI backend starts locally.
* Backend exposes `GET /health`.
* `/health` returns app status, version, and timestamp.
* Backend has a basic test for the health endpoint.

---

## Feature 0.4 — Start Python backend from Electron
Electron should launch the Python backend when the desktop app opens.
### Complete when
* Starting the Electron app also starts the Python backend.
* Closing the Electron app stops the backend.
* Frontend can call `GET /health`.
* UI shows backend status as online/offline.
* Failure to start backend is shown clearly in the UI.
---
## Feature 0.5 — Add basic UI shell
Create the minimal working UI layout.
### Complete when
* App has a clean Obsidian-companion style.
* Sidebar navigation works.
* Dashboard loads without errors.
* Settings page loads without errors.
* No real product behavior is required yet.
---
## Phase 0 acceptance criteria
Phase 0 is complete when:
```text
- Desktop app launches.
- Python backend launches from Electron.
- React frontend can call backend health check.
- Basic navigation exists.
- Tests pass.
- The project can be run by following README instructions.
```

---

# Phase 1 — Vault setup and configuration
## Goal
Allow the user to connect an Obsidian vault and initialize the Simple Wiki folder structure.

## Feature 1.1 — Select Obsidian vault folder
Add vault folder selection.
### Complete when

* User can select a local folder.
* App stores selected vault path.
* App validates that the folder exists.
* App detects whether `.obsidian/` exists.
* App warns, but does not block, if `.obsidian/` is missing.
* Selected vault path appears in Settings and Dashboard.

---

## Feature 1.2 — Create required folders

Create:

```text
Raw/
Wiki/
.llm-wiki/
```

And inside `Wiki/`:

```text
Concepts/
Entities/
Comparisons/
Maps/
Flashcards/
Reviews/
```

### Complete when
* App creates missing folders.
* Existing folders are not overwritten.
* App never modifies unrelated vault folders.
* Folder creation is tested against a temporary fake vault.

---

## Feature 1.3 — Create `index.md` and `log.md`
Create the initial wiki navigation files.

### Complete when
* `Wiki/index.md` is created if missing.
* `Wiki/log.md` is created if missing.
* Existing files are not overwritten.
* Files use clean Obsidian-compatible Markdown.
* Tests verify idempotent behavior.

---

## Feature 1.4 — Create SQLite database

Create `.llm-wiki/app.db`.

### Complete when
* SQLite database is created in `.llm-wiki/`.
* Initial schema migration runs.
* Tables exist for:
  * vaults
  * files
  * extractions
  * chunks
  * wiki_pages
  * proposed_updates
  * audit_events
  * flashcards
  * review_items
* Basic migration test passes.

---

## Feature 1.5 — Store app config

Store local config in `.llm-wiki/config.json`.

### Complete when

* Vault path is persisted.
* Provider settings placeholder exists.
* Model IDs are stored but editable.
* Config loading handles missing/invalid config safely.
* Tests cover config read/write.

---

## Feature 1.6 — Test Groq key

Add Groq API key setup and connection test.

### Complete when

* User can enter Groq API key.
* API key is stored securely using OS keychain where available.
* App can test provider connection.
* UI shows connected/error state.
* Backend does not log the API key.
* Failed connection gives a useful error.

---

## Feature 1.7 — Detect Git
Detect whether the vault is a Git repository.

### Complete when
* App detects `.git/`.
* Dashboard shows Git enabled/not enabled.
* App does not initialize Git automatically.
* App only recommends Git setup.

---

## Feature 1.8 — Detect Obsidian CLI

Detect whether Obsidian CLI is available.
### Complete when
* App checks for Obsidian CLI availability.
* UI shows available/unavailable.
* App explains that core functionality works without it.
* App does not require Obsidian CLI to continue.

---

## Phase 1 acceptance criteria

Phase 1 is complete when:
```text
- User can select a vault.
- Raw/, Wiki/, and .llm-wiki/ are created safely.
- index.md and log.md are created safely.
- SQLite app.db exists.
- Config is stored.
- Groq key can be tested.
- Git and Obsidian CLI status are detected.
- No raw user notes are modified.
- Tests pass.
```

---

# Phase 2 — File watcher and raw ingest

## Goal

Detect files in `Raw/`, extract text from supported file types, and index chunks in SQLite FTS5.

---

## Feature 2.1 — Scan `Raw/`
Scan existing files in `Raw/`.

### Complete when
* App discovers files under `Raw/`.
* App ignores `Wiki/`, `.llm-wiki/`, `.obsidian/`, `.git/`, `.trash/`.
* App shows discovered files in Raw Inbox.
* Tests verify ignored paths.

---

## Feature 2.2 — Hash files
Compute SHA-256 hashes.

### Complete when
* Every discovered file gets a hash.
* Unchanged files are not reprocessed.
* Changed files are detected.
* Hashing is tested.

---

## Feature 2.3 — Watch `Raw/`

Watch for new and changed files.

### Complete when

* New files in `Raw/` appear in Raw Inbox.
* Changed files are queued for reprocessing.
* App waits briefly for file writes to stabilize.
* App does not process generated wiki files.
* Watcher can be started/stopped cleanly.

---

## Feature 2.4 — Extract Markdown and text

Support:

```text
.md
.txt
```

### Complete when
* Markdown and text files are extracted.
* Basic headings are detected.
* Extracted content is stored in SQLite.
* Chunks are stored in FTS5.
* Tests use fixture files.

---

## Feature 2.5 — Extract PDF
Support:

```text
.pdf
```

### Complete when
* PDF text is extracted.
* Page numbers are preserved where possible.
* Empty/scanned PDFs are marked as extraction-limited.
* Extraction errors are shown in Raw Inbox.
* Tests use a sample PDF.

---

## Feature 2.6 — Extract DOCX

Support:

```text
.docx
```

### Complete when
* Paragraphs are extracted.
* Headings are preserved where possible.
* Tables are handled reasonably.
* Chunks are stored with source references.
* Tests use a sample DOCX.

---

## Feature 2.7 — Extract HTML
Support:

```text
.html
.htm
```

### Complete when

* Title and readable body are extracted.
* Script/style/navigation noise is minimized.
* Chunks are stored in FTS5.
* Tests use a sample HTML file.

---

## Feature 2.8 — Extract code and structured text

Support common learning/code files:

```text
.py
.js
.ts
.java
.cpp
.c
.cs
.go
.rs
.json
yaml/yml
csv
```

### Complete when

* Files are treated as learning material when placed in `Raw/`.
* Line references are preserved.
* Large files are chunked safely.
* Tests use small fixture files.

---

## Feature 2.9 — Mark images pending

Support detection for:

```text
.png
.jpg
.jpeg
.webp
```

### Complete when

* Image files appear in Raw Inbox.
* Status is `pending_image`.
* Images are not sent to Groq.
* UI explains image processing is not enabled yet.

---

## Phase 2 acceptance criteria

Phase 2 is complete when:

```text
- App scans Raw/.
- App watches Raw/.
- App ignores protected folders.
- Hash-based reprocessing works.
- Markdown, text, PDF, DOCX, HTML, code, JSON/YAML/CSV are extracted.
- Images are marked pending.
- Extracted chunks are stored in SQLite FTS5.
- Raw files are never modified.
- Tests pass.
```

---

# Phase 3 — Wiki generation

## Goal

Convert raw extracted content into concise wiki knowledge pages.

---

## Feature 3.1 — Identify wiki candidates

Use Groq to identify:

```text
Concepts
Entities
Comparisons
Maps
Flashcard opportunities
```

### Complete when

* Backend sends extracted text to Groq.
* Response is parsed into structured candidates.
* Candidates are shown in processing output.
* Invalid LLM responses fail safely.
* Tests cover parser behavior with mocked LLM output.

---

## Feature 3.2 — Create new concept pages

Create new pages in:

```text
Wiki/Concepts/
```

### Complete when

* New concept pages are created automatically.
* Pages are concise.
* Pages use Obsidian `[[Wiki Links]]` when relevant.
* Pages include a Sources section.
* App avoids duplicate page names.
* Tests verify Markdown output.

---

## Feature 3.3 — Create new entity pages

Create new pages in:

```text
Wiki/Entities/
```

### Complete when

* Entity pages are created automatically.
* Pages are short and source-cited.
* Duplicate entity pages are avoided.
* Tests verify output path and content.

---

## Feature 3.4 — Create comparison pages

Create new pages in:

```text
Wiki/Comparisons/
```

### Complete when

* Comparison pages are created when useful.
* Pages are concise.
* Tables are allowed when helpful.
* Sources are cited.
* Tests verify Markdown output.

---

## Feature 3.5 — Create map pages

Create new pages in:

```text
Wiki/Maps/
```

### Complete when

* Map pages are created only when useful.
* Maps are outline-style and short.
* Maps link to concepts/entities.
* Sources are cited.

---

## Feature 3.6 — Update index

Update `Wiki/index.md`.

### Complete when

* New pages appear in `index.md`.
* Each index entry has a one-line summary.
* Existing index entries are not duplicated.
* Index remains human-readable.
* Tests verify idempotent updates.

---

## Feature 3.7 — Append log event

Update `Wiki/log.md`.

### Complete when

* Meaningful ingest/update event is appended.
* Log includes source path, generated pages, timestamp, and status.
* Log does not include noisy internal details.
* Tests verify append behavior.

---

## Feature 3.8 — Generate flashcards

Create flashcards in:

```text
Wiki/Flashcards/
```

### Complete when

* Flashcards are generated per source or concept.
* Cards are concise.
* Answers cite sources.
* No Anki export is required.
* Tests verify Markdown output.

---

## Phase 3 acceptance criteria

Phase 3 is complete when:

```text
- A raw source can create new concept/entity/comparison/map pages.
- New pages are created automatically.
- Pages are concise and cited.
- index.md is updated.
- log.md is updated.
- Flashcards are generated.
- No existing wiki page is overwritten yet.
- Tests pass with mocked Groq responses.
```

---

# Phase 4 — Existing page update review

## Goal

Allow the app to improve existing wiki pages, but only after user approval.

---

## Feature 4.1 — Detect related existing pages

Find existing wiki pages related to new source content.

### Complete when

* App searches existing Wiki pages using FTS5.
* Related pages are ranked.
* App avoids unrelated updates.
* Tests use fixture wiki pages.

---

## Feature 4.2 — Generate proposed update

Generate a proposed replacement or patch for an existing page.

### Complete when

* Existing page is not modified directly.
* Proposed update is stored in `.llm-wiki/cache/proposed-updates/` or SQLite.
* Proposal includes reason for change.
* Proposal includes source citation.
* Tests verify no write happens to original page.

---

## Feature 4.3 — Show visual diff

Add diff viewer in Proposed Updates screen.

### Complete when

* User can see current page and proposed version.
* Added/removed/changed content is visible.
* Source citation is visible.
* User can reject without side effects.

---

## Feature 4.4 — Approve one update

Allow approving one proposed update.

### Complete when

* Approved update writes to the target Markdown file.
* Audit event is recorded.
* index.md/log.md update if needed.
* Rejected updates do not write files.
* Tests verify write behavior.

---

## Feature 4.5 — Approve all updates

Allow approving all proposed updates from an ingest run.

### Complete when

* User can approve all pending updates for a source.
* Each write is audited.
* Failure on one update does not corrupt others.
* UI shows success/error state.

---

## Feature 4.6 — Audit every write

Write audit records.

### Complete when

* Every generated file write creates an audit event.
* Audit includes timestamp, source file, target file, action, and model.
* Audit is written to SQLite and `.llm-wiki/audit.jsonl`.
* Tests verify audit output.

---

## Phase 4 acceptance criteria

Phase 4 is complete when:

```text
- Existing related pages are detected.
- Proposed updates are generated without modifying files.
- User can view visual diffs.
- User can approve one update.
- User can approve all updates.
- Rejected updates make no changes.
- Every write is audited.
- Tests pass.
```

---

# Phase 5 — Ask

## Goal

Provide wiki-first instant answers without automatically saving answers.

---

## Feature 5.1 — Build Ask UI

Create the Ask screen.

### Complete when

* User can enter a question.
* UI shows loading, answer, citations, and errors.
* No answer is saved automatically.

---

## Feature 5.2 — Search wiki first

Use `Wiki/index.md` mirror and Wiki FTS.

### Complete when

* Ask searches wiki pages first.
* Relevant wiki pages are loaded.
* Raw chunks are not used initially.
* Tests verify wiki-first retrieval order.

---

## Feature 5.3 — Load graph neighbors

Load linked pages around the top results.

### Complete when

* App detects `[[Wiki Links]]`.
* Neighbor pages are loaded when useful.
* Retrieval remains token-efficient.
* Tests cover link parsing.

---

## Feature 5.4 — Verify with raw chunks

Use raw chunks only when needed.

### Complete when

* Raw chunks are used for citations or verification.
* Answer prompt prioritizes wiki pages.
* Raw chunks are clearly secondary.
* Tests verify retrieval layering.

---

## Feature 5.5 — Generate answer with citations

Use Groq to answer.

### Complete when

* Answer cites wiki pages and raw sources where available.
* Unsupported answers say they are unsupported.
* App does not hallucinate citations.
* Tests use mocked LLM output.

---

## Feature 5.6 — Add “Propose wiki update”

Add optional button.

### Complete when

* User can convert an Ask answer into a proposed wiki update.
* Nothing is written automatically.
* Proposal enters the same review workflow as Phase 4.

---

## Phase 5 acceptance criteria

Phase 5 is complete when:

```text
- Ask screen works.
- Answers are generated from wiki pages first.
- Raw chunks are used only for verification/citations.
- Answers include citations.
- Answers are not saved automatically.
- “Propose wiki update” creates a reviewable proposal.
- Tests pass.
```

---

# Phase 6 — Lint

## Goal

Automatically maintain wiki health after ingest.

---

## Feature 6.1 — Auto-run lint after ingest

Trigger lint after processing.

### Complete when

* Lint runs after successful ingest.
* Lint status appears in Dashboard.
* Lint failure does not break ingest.
* Tests verify lint trigger.

---

## Feature 6.2 — Detect broken mechanical issues

Detect:

```text
Missing index entries
Broken internal links
Missing obvious backlinks
Empty duplicate pages
```

### Complete when

* Lint finds mechanical issues.
* Issues are stored in SQLite.
* UI shows issue count.
* Tests use fixture wiki.

---

## Feature 6.3 — Auto-fix safe issues

Fix only safe broken issues.

### Complete when

* Missing index entries can be fixed.
* Obvious broken links can be fixed.
* Fixes are audited.
* Semantic issues are not auto-fixed.
* Tests verify safe/unsafe boundaries.

---

## Feature 6.4 — Create Review pages for semantic issues

Create pages in:

```text
Wiki/Reviews/
```

For:

```text
Contradictions
Stale claims
Uncited claims
Duplicate concepts needing judgment
Overlong pages
Low-confidence concepts
```

### Complete when

* Review pages are created for semantic issues.
* Affected concept page is not modified directly.
* Review page cites relevant sources/pages.
* Tests verify Review page creation.

---

## Phase 6 acceptance criteria

Phase 6 is complete when:

```text
- Lint auto-runs after ingest.
- Mechanical issues are detected.
- Safe mechanical issues are auto-fixed.
- Semantic issues create Review pages.
- Lint status appears in UI.
- Every auto-fix is audited.
- Tests pass.
```

---

# Phase 7 — Git

## Goal

Add optional version history for wiki changes.

---

## Feature 7.1 — Optional Git setup

Offer Git setup in Settings.

### Complete when

* App detects whether vault is a Git repo.
* User can enable/disable Git integration.
* App does not force Git.
* App explains what will be committed.

---

## Feature 7.2 — Checkpoint before approved updates

Create checkpoint before writing approved updates.

### Complete when

* Before applying approved updates, app creates checkpoint commit if Git is enabled.
* Commit includes only allowed files.
* Failure to commit does not corrupt wiki.
* UI shows warning if checkpoint fails.

---

## Feature 7.3 — Commit after updates

Commit generated wiki changes.

### Complete when

* After successful writes, app commits generated Markdown and audit log.
* Commit message is clear.
* `app.db` and cache are not committed.
* Raw files are not committed unless user explicitly opts in.

---

## Feature 7.4 — Git ignore rules

Create or update `.gitignore` safely.

### Complete when

* `.llm-wiki/app.db` is ignored.
* `.llm-wiki/cache/` is ignored.
* `.llm-wiki/audit.jsonl` can be committed.
* Existing `.gitignore` content is preserved.

---

## Phase 7 acceptance criteria

Phase 7 is complete when:

```text
- Git integration is optional.
- App can checkpoint before approved updates.
- App can commit after updates.
- app.db and cache are not committed.
- Wiki/ and audit logs are committed by default.
- Raw/ is not committed unless user opts in.
- Tests pass using a temporary Git repo.
```

---

# Phase 8 — Packaging

## Goal

Ship installable desktop builds.

---

## Feature 8.1 — Bundle Python backend

Package Python backend with desktop app.

### Complete when

* Electron build includes Python backend.
* App can start backend from packaged build.
* Backend path resolution works cross-platform.

---

## Feature 8.2 — Package Electron app

Create desktop installers.

### Complete when

* Windows build works.
* macOS build works.
* Linux build works.
* App launches from installed package.
* Health check works in packaged app.

---

## Feature 8.3 — Document Obsidian CLI optional setup

Add user docs.

### Complete when

* Docs explain that Obsidian CLI is optional.
* Docs explain core features work without it.
* Docs explain Obsidian must be running for CLI features.
* Settings page links to docs.

---

## Phase 8 acceptance criteria

Phase 8 is complete when:

```text
- App can be packaged.
- Packaged app starts frontend and backend.
- Installers work on target platforms.
- User docs explain setup clearly.
- Obsidian CLI is documented as optional.
```

---

# Phase 9 — Android v2

## Goal

Build Android version with the same product behavior.

---

## Feature 9.1 — Create Expo app

Create Android app shell.

### Complete when

* Expo app starts.
* UI mirrors desktop structure.
* Navigation exists for:

  * Dashboard
  * Raw Inbox
  * Proposed Updates
  * Wiki Browser
  * Ask
  * Lint
  * Settings

---

## Feature 9.2 — Add Android vault folder access

Use Android folder picker/access.

### Complete when

* User can select Obsidian vault folder.
* App can read/write allowed files.
* App creates Raw/, Wiki/, .llm-wiki/.
* Permission errors are handled clearly.

---

## Feature 9.3 — Share schema and prompts

Use shared schema/prompt files.

### Complete when

* Android uses the same page rules as desktop.
* Prompt files are shared or copied from `packages/shared`.
* Behavior stays consistent with desktop.

---

## Feature 9.4 — Implement Android ingest

Implement or reimplement backend logic.

### Complete when

* Android can scan Raw/.
* Android can extract supported non-image files where practical.
* Images are marked pending.
* Chunks are indexed locally.
* Groq processing works.

---

## Feature 9.5 — Implement Android wiki write/review

Add same review behavior.

### Complete when

* New pages are created automatically.
* Existing page updates require approval.
* Diff viewer works.
* Writes go directly to the vault folder.

---

## Feature 9.6 — Implement Android Ask and lint

Add Ask and lint behavior.

### Complete when

* Ask is wiki-first.
* Raw chunks are secondary.
* Answers are not auto-saved.
* Lint detects/fixes safe issues.
* Review pages are created for semantic issues.

---

## Phase 9 acceptance criteria

Phase 9 is complete when:

```text
- Android app can connect to the same Obsidian vault folder.
- Android can create Raw/, Wiki/, .llm-wiki/.
- Android can ingest supported files.
- Android can create and update wiki pages.
- Existing page updates require review.
- Android Ask works.
- Android lint works.
- Android uses Groq.
- Android does not depend on Obsidian CLI.
```

---

# Final implementation rule

A phase is not complete because code exists.

A phase is complete only when:

```text
- The feature works end-to-end.
- Tests cover the behavior.
- The UI exposes the behavior clearly.
- Errors are handled.
- Raw/ is never modified.
- Writes are limited to Wiki/ and .llm-wiki/.
- The implementation is simple enough to maintain.
```
