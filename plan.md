# Local LLM Wiki for Obsidian - Working Plan

## Purpose

Build a local-first desktop app that connects to an existing Obsidian vault, treats existing notes and imported files as immutable raw sources, and creates a separate generated wiki layer inside the same vault.

This document synthesizes:

- the source implementation plan in `local_llm_wiki_obsidian_implementation_plan.md`
- the current implementation decisions given in the interview answers

Where the interview answers were incomplete, this file uses the source plan as the default implementation assumption.

## MVP Definition

The narrowest acceptable MVP is:

- a Python desktop app using PySide6 or PyQt6
- user selects an existing Obsidian vault
- app creates `LLM Wiki/` and `.llm-wiki/`
- app scans and watches supported raw source files
- app ignores generated/app-owned folders
- app extracts content from supported files
- app stores file state in SQLite
- app generates one source-summary Markdown page per source
- app writes generated content automatically into app-owned folders
- app writes summaries into `LLM Wiki/Sources/`
- app logs generated writes

Explicitly out of scope for MVP:

- cloud sync
- multi-user accounts
- Clerk authentication
- Vercel or Netlify deployment
- automatic concept pages
- automatic topic maps
- automatic updates across all generated concept pages
- editing raw user notes
- rollback button
- advanced prompt and model settings UI
- full Obsidian plugin
- mobile app

## Architecture Decision

The MVP will start as a desktop app instead of a web app or Obsidian plugin.

Reasons:

- it keeps the system local-first by default
- it avoids plugin-specific integration complexity during the first version
- it matches the preferred implementation language: Python
- it reduces moving parts compared with a browser frontend plus backend split
- it is simpler for non-technical users than running a dev server or managing extra setup

Recommended stack:

- UI: PySide6 or PyQt6
- local services: Python modules in the same app process
- file watching: `watchdog`
- storage: Markdown in the vault plus SQLite in `.llm-wiki/app.db`
- packaging: PyInstaller or Briefcase later
- LLM provider: Groq first, with abstraction for OpenAI and Ollama

## Non-Negotiable Safety Rules

Raw notes are immutable.

The app must never:

- edit raw notes
- rename raw notes
- move raw notes
- delete raw notes
- overwrite raw notes

The app may write only to app-owned locations for MVP:

- `LLM Wiki/`
- `.llm-wiki/`

Generated content must never be written outside app-owned folders.

## Vault Structure

Required vault structure:

```text
Obsidian Vault/
  LLM Wiki/
    _Index.md
    _Inbox.md
    _Processing Log.md
    Sources/
    Questions/
    Flashcards/
    Active Recall/
    Audit/
  .llm-wiki/
    app.db
    config.json
    file_index.json
    logs/
```

User-facing locations:

- `LLM Wiki/`
- `LLM Wiki/Sources/`
- `LLM Wiki/Questions/`
- `LLM Wiki/Flashcards/`
- `LLM Wiki/Active Recall/`
- `LLM Wiki/Audit/`
- `LLM Wiki/_Index.md`
- `LLM Wiki/_Inbox.md`
- `LLM Wiki/_Processing Log.md`

App-internal locations:

- `.llm-wiki/`
- `.llm-wiki/app.db`
- `.llm-wiki/config.json`
- `.llm-wiki/file_index.json`
- `.llm-wiki/logs/`

## File Watching and Exclusions

The watcher monitors the selected vault for new or changed supported files.

The watcher must ignore:

- `LLM Wiki/`
- `.llm-wiki/`
- `.obsidian/`
- `.git/`
- `.trash/`

Why this matters:

- without excluding `LLM Wiki/`, generated files can be re-ingested as raw sources and create recursive summary loops
- without excluding `.llm-wiki/`, internal metadata changes can trigger useless processing churn
- without excluding `.obsidian/` and `.git/`, normal editor and repo activity creates noise and false processing events
- without excluding trash-like folders, deleted or transient files may be processed incorrectly

## Supported Inputs

MVP-supported file types:

- `.md`
- `.txt`
- `.pdf`
- `.docx`
- `.html`
- `.htm`
- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

Processing expectations:

- Markdown and text: read directly
- PDF: extract text and preserve page references where possible
- DOCX: extract paragraphs, headings, and tables where feasible
- HTML: extract readable text from web clips or exports
- images: use vision-capable extraction or description flow

## End-to-End Processing Flow

New file or changed file flow:

1. Watcher detects filesystem change.
2. Ignore the event if the path is inside excluded folders.
3. Wait briefly for the write to become stable.
4. Confirm the file type is supported.
5. Compute SHA-256 hash.
6. Check the `files` table.
7. Skip processing if the same content hash was already processed.
8. Insert or update the file record with a queued or processing state.
9. Extract content based on file type.
10. Store extracted text and metadata in `source_documents`.
11. Chunk the extracted content.
12. Store chunks in `chunks`.
13. Call the LLM to generate a source summary.
14. For later MVP stages, also generate flashcards and active recall questions.
15. Write generated Markdown into `LLM Wiki/`.
16. Record the generated file in `generated_pages`.
17. Update `LLM Wiki/_Index.md`.
18. Append an entry to `LLM Wiki/_Processing Log.md`.
19. Append an audit event.
20. Optionally commit generated files if Git integration is enabled.
21. Mark the source file as processed.

## Why Hash-Based Processing

Hash-based processing is required because timestamps alone are not reliable.

Benefits:

- detects real content changes instead of timestamp noise
- avoids false positives from editor saves, sync tools, or metadata-only changes
- avoids false negatives when timestamps are preserved during copy, restore, or sync
- gives the app a deterministic basis for reprocessing decisions

## SQLite Schema Priorities

Essential MVP tables:

- `vaults`: selected vault metadata
- `files`: raw source paths, hashes, type, status, timestamps, and processing errors
- `source_documents`: extracted text and extraction metadata per source file
- `chunks`: smaller searchable source segments for retrieval and citation
- `generated_pages`: generated Markdown written to the vault
- `audit_log`: trace of generated writes and related sources

Useful but lower-priority for later MVP phases:

- `qa_history`
- `flashcards`
- `active_recall_questions`

### Table Responsibilities

`source_documents`

- canonical extracted content for a raw file
- stores extracted text and extraction metadata

`chunks`

- searchable subdivisions of extracted content
- supports retrieval and citation grounding

`generated_pages`

- records generated outputs that actually exist in `LLM Wiki/`
- tracks path, page type, and content hash

## Post-Write Inspection

This plan intentionally removes pre-write approval from MVP.

Safety now comes from:

- path ownership enforcement
- generated-folder exclusion in the watcher
- source-grounded prompts and citations
- audit logging for every generated write

The app should still let the user inspect generated files after write.

Minimum inspection fields:

- target file path
- source file path
- generated Markdown preview
- citations or source references
- processing timestamp
- error state when generation fails

## Retrieval and Q&A Strategy

Retrieval order:

1. search generated summaries first
2. search raw source chunks second
3. build a grounded prompt with citations
4. answer using retrieved evidence only

Why summaries first:

- they are compressed, learner-oriented, and faster to search
- they often capture the answer in a more directly usable form

Why raw chunks remain source of truth:

- summaries are derived artifacts and can omit nuance
- citations must be defensible against original material
- Q&A must say "not supported" if the raw evidence is insufficient

Saved answers, if retained, should go into `LLM Wiki/Questions/`.

## Provider Strategy

Current provider plan:

- Groq is the default provider for MVP
- provider abstraction must exist from the start
- future providers include OpenAI and Ollama

Implementation rule:

- do not hardcode model names throughout the codebase
- keep provider settings and model identifiers in config
- the app should be able to swap providers without restructuring ingestion or retrieval code

## One-Summary-Per-Source Constraint

For MVP, each raw source gets one summary page.

This prevents the project from becoming too early:

- concept graph builder
- automatic topic-map generator
- cross-document synthesis engine
- broad rewrite system for generated pages

That constraint reduces scope, lowers update complexity, and keeps traceability straightforward.

## First Five Milestones

Implementation order should follow the source plan exactly enough to preserve safety and momentum.

### Milestone 1: App Skeleton and Vault Setup

- create desktop app shell
- add first-run wizard
- select vault path
- create required folders
- store config

### Milestone 2: SQLite and File Indexing Foundation

- create `app.db`
- implement schema for `vaults`, `files`, `source_documents`, `chunks`, `generated_pages`, `audit_log`
- implement vault scan
- implement supported-file filtering
- implement excluded-folder filtering
- implement hash-based indexing

### Milestone 3: Markdown and Text Ingestion

- parse `.md` and `.txt`
- store extracted text
- chunk extracted content
- create processing queue
- create one automatic source-summary write

### Milestone 4: Automatic Write and Audit Path

- write generated files into `LLM Wiki/Sources/`
- update `_Index.md` and `_Processing Log.md`
- append audit log entries
- surface recent generation activity and errors

### Milestone 5: Broader Ingestion and LLM Features

- add PDF ingestion
- add DOCX ingestion
- add HTML ingestion
- add image ingestion
- add flashcard generation
- add active-recall generation
- add Q&A with citations
- add optional Git integration

## Main Risks

Highest-risk technical and product failure modes:

- recursive ingestion of generated files if exclusions are wrong
- accidental writes to raw notes if path ownership is not enforced centrally
- weak citation grounding, especially for PDFs and images
- unstable extraction quality across PDF, DOCX, and HTML formats
- duplicate processing caused by noisy file watcher events
- user anxiety because generated files appear automatically without a review gate
- provider-specific behavior leaking through the abstraction layer
- poor title and filename normalization causing broken Obsidian links
- low-value summaries if prompts are not constrained to source-grounded outputs
- Q&A appearing authoritative when the raw evidence is partial or missing

## Immediate Build Guidance

Do first:

- desktop skeleton
- vault selection
- folder creation
- SQLite schema
- initial vault scan
- excluded-folder handling
- hash-based indexing
- Markdown and text ingestion
- one summary automatic-write workflow

Do later:

- PDF, DOCX, HTML, image ingestion
- flashcards
- active recall
- Q&A
- Git integration
- packaging

## Open Questions

These are not blockers, but they should be resolved during implementation:

- exact title-to-filename normalization rules for generated pages
- whether `_Inbox.md` is required in the first coded milestone or only as a placeholder
- whether embeddings are needed in the first Q&A pass or simple text retrieval is enough
- how image extraction quality will be validated across providers
