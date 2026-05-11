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
* Scan only reads files and never modifies anything under `Raw/`.
* App shows discovered files in Raw Inbox.
* Scan results are persisted so later hashing/extraction work uses the same discovered file set.
* Tests verify ignored paths.

---

## Feature 2.2 — Hash files
Compute SHA-256 hashes.

### Complete when
* Every discovered file gets a hash.
* Unchanged files are not reprocessed.
* Changed files are detected.
* Reprocessing decisions are based on stored hashes, not file names or timestamps alone.
* Hashing does not modify source files.
* Hashing is tested.

---

## Feature 2.3 — Watch `Raw/`

Watch for new and changed files.

### Complete when

* New files in `Raw/` appear in Raw Inbox.
* Changed files are queued for reprocessing.
* App waits briefly for file writes to stabilize.
* App does not process generated wiki files.
* Watcher applies the same protected-folder exclusions as the initial scan.
* Watcher only schedules read/ingest work and never writes into `Raw/`.
* Watcher can be started/stopped cleanly.
* Tests cover create/change events, stabilization delay, and protected-folder exclusions.

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
* Extracted chunks are stored in SQLite FTS5 with source file references.
* Raw source files are not modified during extraction or chunking.
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
* Extracted text and chunks are stored in SQLite FTS5 with page-aware source references when available.
* Raw PDF files are not modified during extraction.
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
* Chunks are stored in SQLite FTS5 with source references.
* Raw DOCX files are not modified during extraction.
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
* Chunks are stored in SQLite FTS5 with source references.
* Raw HTML files are not modified during extraction.
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
.yaml
.yml
.csv
```

### Complete when

* Files are treated as learning material when placed in `Raw/`.
* Line references are preserved.
* Large files are chunked safely.
* Extracted chunks are stored in SQLite FTS5 with source references.
* Raw source files are not modified during extraction or chunking.
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
* Image files are not chunked or inserted into text-extraction tables.
* Tests verify `pending_image` status and no text extraction side effects.

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

Allow the app to safely improve existing wiki pages when new, updated, versioned, removed, or weakened raw sources affect already-compiled knowledge.

When a new or changed raw source affects existing wiki pages, the app must not immediately rewrite those pages.

Instead, it must:

1. Detect which existing wiki pages are related to the source.
2. Decide whether the source creates a meaningful knowledge change.
3. Generate proposed updates for affected pages.
4. Store proposed updates without modifying the original Markdown files.
5. Show the user a visual diff.
6. Let the user approve or reject each proposal.
7. Apply only approved updates.
8. Leave rejected updates with no side effects.
9. Audit every proposal, decision, and file write.

The files that requires review/proposal are placed in /Reviews folder

---

## Feature 4.1 — Detect related existing pages

When new file is added to /raw folder, find existing wiki pages related to new source content. If not, generate new wiki pages. do not update unnrelated pages. record why each page was selected

### Complete when

* App searches existing Wiki pages using FTS5.
* App ranks candidate pages.
* App avoids unrelated updates.
* Tests use fixture wiki pages.
* Candidates are filtered before review is generated for each file

---

## Feature 4.2 — Generate proposed update

If there are candidates that needs update then for each related page, generate a proposed update. The page is created in Review folder as diff. Store the proposed update in SQLite.\
Existing page must not be modified without approval. Proposal must explain why the update is needed. The proposal must cite the source

### Complete when

* Original markdown files are unchanged.
* Proposed update is stored in `.llm-wiki/cache/proposed-updates/` or SQLite.
* Proposal includes reason for change.
* Proposal includes source citation.
* Tests verify no write happens to original page.

---

## Feature 4.3 — Show visual diff

Add diff viewer in Proposed Updates screen where user can compare the previous and updated version. Show all the proposed changes in red and green color.
For each update, the user should see the source file, target wiki page, reason for update, current content, proposed content and visual diff. 
The user can approve, reject or leave it as pending (do not process)

- After user clicks accept, the page is updated with new content. 
- Rejecting must not change any wiki file
- User must be able to understand what will change before approving

### Complete when

* User can see current page and proposed version.
* The diff viewer shows added/removed/changed content with colors.
* Source citation is visible.
* User can reject without side effects.
* Tests verify rejected proposals do not write files.

---

## Feature 4.4 - Edit Proposed Update
All the user to modify the generated proposal/update before accepting. The user should see an option to edit the proposed update, clicking that will open the proposed update in a text editor with current and proposed content. User can edit the proposed content. 

### Complete when

* User can edit the proposed update.
* Edited proposal is persisted.
* Accepting an edited proposal writes the edited version.
* Rejecting edited proposal does not write files.
* Tests verify edit + accept behavior.

---

## Feature 4.5 — Approve one update

Allow approving one proposed update.

### Conflict rule
If target file changes after proposal was created, do not write. instead show 
```text
⚠️ Conflict: Target page was updated by another process after this proposal was generated. Approve again to regenerate and apply.

Source: 
Original target: 
Updated target: 

Regenerate and apply?
```

### Complete when

* Approved update writes to the target Markdown file.
* Mechanism to prevent unsafe write
* Audit event is recorded.
* index.md/log.md update if needed.
* Rejected updates do not write files.
* Tests verify write behavior.

---

## Feature 4.6 — Approve all updates

Allow user to approve all pending proposals for one ingest run or source. Apply each proosal independently and if one fails, continue with others
Audit each write separately. Do not corrupt other updates. Show result per proposal (success/failure)


Example result:
```text
7 applied
2 skipped due to hash conflict
1 failed due to filesystem error
```

### Complete when

* User can approve all pending updates for a source.
* Each write is audited.
* Partial failure is handled safely.
* Failure on one update does not corrupt others.
* UI shows success/error state.

---

## Feature 4.7 — Audit every write

Write audit records.
Write audit events to both:
```text
SQLite
.llm-wiki/audit.jsonl
```
Audit these events:

```text
proposal_created
proposal_approved
proposal_rejected
proposal_conflicted
proposal_failed
target_file_written
index_updated
log_updated
```

Audit record must include
```text
timestamp
event_type
proposal_id
ingest_run_id
source_file
source_id
source_version
target_file
action
model
old_hash
new_hash
status
Complete when
Every proposal lifecycle event is audited.
Every file write is audited.
Audit exists in SQLite and JSONL.
Tests verify audit output.
```

## Feature 4.8 - Reject Update and remove from review

Allow user to reject updates. The proposal is marked rejected and timestamp rejection is stored. Do not modfiy target markdown file and append audit event with action rejected


### Complete when

* User can reject updates.
* Rejected updates are removed from review.
* Audit event is recorded.
* Rejected proposal no longer appears in default pending list.
* Tests verify rejected updates do not write files.


## Feature 4.9 - Update index.md and log.md
After approved updates, update index.md and log.md if needed. Do not update index/log for rejected proposals. Audit index/log writes.

### Complete when

* index.md and log.md are updated after approved updates.
* index.md and log.md are not updated for rejected proposals.
* Audit event is recorded.
* Tests verify index.md and log.md update behavior.

---

## Phase 4 acceptance criteria

Phase 4 is complete when:

```text
- Source identity and versions are tracked.
- Source updates are detected by hash.
- Meaningful source changes are summarized.
- Related existing wiki pages are found using FTS5.
- Unrelated pages are avoided.
- Proposed updates are generated without modifying wiki files.
- Proposals include reason, citation, target file, affected claims, confidence, and update type.
- User can view visual diffs.
- User can approve one update.
- User can reject one update.
- User can approve all updates from an ingest run.
- Rejected updates make no file changes.
- Hash conflicts prevent unsafe writes.
- Removed or weakened evidence creates provenance/confidence proposals.
- index.md and log.md update only after approved writes.
- Every decision and write is audited.
- Tests pass.
```

---

# Phase 5 — Ask

## Goal

Provide wiki-first instant answers without automatically saving answers.

## Phase 5 delivery rule

Implement Phase 5 strictly in this order:

```text
5.1 Ask UI shell
5.2 Wiki-first retrieval
5.3 Graph-neighbor expansion
5.4 Raw-source verification
5.5 Answer generation with citations
5.6 Propose wiki update
```

Do not start the next feature until the current feature:

* has targeted tests added first or updated first
* passes the smallest relevant backend and frontend checks
* is manually verified in the desktop app
* proves that a plain Ask run does not write Wiki/ content automatically

## Phase 5 implementation plan

### Feature 5.1 implementation sequence

1. Define the Ask request/response contract first, including question text, answer body, citations, unsupported-answer state, and trace metadata that stays internal to the app.
2. Add or update tests first for empty-question validation, success payload shape, error handling, loading state transitions, and the rule that Ask does not persist an answer by default.
3. Add the minimal backend route and Electron bridge for Ask before any retrieval logic so the UI can be built against a stable typed contract.
4. Build the Ask screen as a focused UI slice with question input, submit action, loading state, answer panel, citation list, and error state. Keep renderer logic in dedicated Ask modules instead of growing unrelated logic in one file.
5. Verify the feature by submitting a mocked successful question, an empty question, and a forced backend failure, then confirm no wiki page, review file, or audit write happens from Ask alone.

### Feature 5.2 implementation sequence

1. Add or update retrieval tests first for wiki-first ranking, empty-result handling, and the rule that raw chunks are not queried during the first retrieval stage.
2. Implement Ask retrieval in backend service modules, not in the route. Reuse `wiki_pages_fts` first and add `index.md` mirroring support only if the current schema cannot satisfy the `Wiki/index.md -> wiki pages -> raw verification` order from `IMPLEMENTATION_PLAN.md`.
3. Return a retrieval trace that distinguishes selected wiki pages from any later raw verification so tests can assert the ordering deterministically.
4. Keep the first working version narrow: select top wiki candidates, deduplicate them, and cap payload size before sending anything to the LLM.
5. Verify the feature with fixture wiki pages and confirm the first retrieval stage succeeds without touching raw chunk search.

### Feature 5.3 implementation sequence

1. Add or update tests first for `[[Wiki Links]]` parsing, duplicate-neighbor suppression, and token-budget limits on neighbor expansion.
2. Implement neighbor loading as a second wiki-only step after primary wiki search. Do not mix it with raw-source verification.
3. Prefer deterministic neighbor selection: direct outgoing links first, then optional backlinks only if the current data model supports them safely.
4. Keep neighbor enrichment bounded so the answer context remains concise and predictable.
5. Verify the feature by tracing a result set that loads the expected linked pages without inflating context unnecessarily.

### Feature 5.4 implementation sequence

1. Add or update tests first for retrieval layering, source deduplication, citation-anchor preservation, and the rule that raw chunks stay secondary to wiki evidence.
2. Implement raw verification as an explicit second-stage retrieval pass that runs only when the answer path needs citation support or wiki context is insufficient.
3. Query `chunks_fts` with bounded limits, preserve page/section/line anchors, and keep the selected raw evidence separate from wiki evidence in the response contract.
4. Fail closed when citation anchors cannot be mapped back to a real raw source location.
5. Verify the feature by confirming a wiki-backed answer can complete without raw retrieval, while a citation-sensitive answer pulls only the minimum supporting raw chunks.

### Feature 5.5 implementation sequence

1. Add or update tests first for supported answers, unsupported answers, invalid structured LLM output, and citation validation with mocked provider responses.
2. Add the Ask prompt contract in shared prompts and keep the backend call inside `LLMProvider`. The route should orchestrate services only.
3. Require the answer generator to cite the evidence it actually received. If the model cannot support the answer from retrieved context, return an explicit unsupported result instead of a weak synthesis.
4. Keep the first shipped version non-streaming unless streaming is required to make the feature usable.
5. Verify the feature by checking that answers cite wiki pages and raw sources correctly, unsupported answers stay explicit, and fabricated citations are rejected.

### Feature 5.6 implementation sequence

1. Add or update tests first for the “Propose wiki update” action, including the rule that it creates a reviewable proposal and never writes directly to an existing wiki page.
2. Reuse the Phase 4 review workflow instead of creating a parallel Ask-specific update path. Ask should hand off answer text, evidence, and target metadata into the existing proposal system.
3. Keep Ask state ephemeral unless the user explicitly requests a follow-up action. Do not add durable Ask history as part of this feature.
4. Disable the action when the answer is unsupported or lacks enough grounded evidence to create a safe proposal.
5. Verify the feature by creating a proposal from an Ask answer, confirming it appears in the pending review list, and confirming that ordinary Ask usage still produces no automatic writes.

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
