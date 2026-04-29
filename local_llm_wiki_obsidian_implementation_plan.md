# Local LLM Wiki for Obsidian — Project Description & Implementation Plan

## 1. Product summary

Build a local-first desktop app that connects to a user's existing Obsidian vault, treats their notes and imported files as immutable raw sources, and creates an LLM-maintained wiki layer inside the same vault.

The first MVP should focus on the smallest useful version of the Karpathy-style LLM wiki concept:

1. Raw documents remain untouched.
2. The app automatically creates source-summary wiki pages.
3. The app maintains an index so users can retrieve, ask questions about, and inspect their learning material.
4. The generated wiki is stored as normal Markdown inside the Obsidian vault.
5. The experience should be simple enough for non-technical users.

The app should run locally as a desktop application. User notes stay on the user's machine. LLM calls may require the internet depending on the configured provider, such as Groq, but the user's vault should remain local and under their control.

---

## 2. Core product goals

### Primary goal

Help users learn from their notes by turning messy or scattered Obsidian notes into an organized, source-grounded LLM wiki.

### Initial target user

The first target user is the project owner. The product should later be extendable to general Obsidian users, especially non-technical learners.

### Main use case

Learning new things from personal notes, study material, PDFs, text notes, images, web clips, and other imported knowledge sources.

### Product shape

A local desktop app that:

- Lets the user select an Obsidian vault folder.
- Automatically creates required LLM Wiki folders inside that vault.
- Watches the vault for new or changed raw source files.
- Processes supported source files.
- Generates one source-summary Markdown page per raw source.
- Writes generated wiki files into the Obsidian vault.
- Never modifies user-authored raw notes.
- Keeps a SQLite index and audit log.
- Automatically writes generated content into app-owned wiki folders.
- Supports Q&A over the generated wiki and indexed raw sources.
- Generates active-recall questions and flashcards for learning.

---

## 3. Important product constraints

### Local-first

The app must run locally. The selected Obsidian vault remains on the user's machine.

### Raw notes are immutable

The app must never edit, rewrite, delete, rename, or move user-authored raw notes.

The app may only write inside app-owned/generated folders unless the user explicitly configures otherwise.

### Generated wiki is separate

Generated content must live in a dedicated folder inside the vault, such as:

```text
LLM Wiki/
```

### One summary page per source in MVP

For MVP, do not automatically generate broader concept pages like:

```text
LLM Wiki/Concepts/Backpropagation.md
LLM Wiki/Learning Maps/Neural Networks.md
```

Instead, create one source-summary page per raw document, for example:

```text
LLM Wiki/Sources/Backpropagation summary.md
```

### Preserve Obsidian compatibility

Generated Markdown should use Obsidian-compatible conventions, including:

- `[[Wiki Links]]`
- Normal Markdown headings
- Optional Markdown tables
- Internal links to generated source summaries
- Relative links to source files where possible

### Source grounded

All generated summaries and answers should include source references back to the raw source file and, when possible, section/page/chunk references.

### Non-technical setup

The first-run flow should be simple:

1. Open desktop app.
2. Select Obsidian vault folder.
3. Enter or configure LLM provider key.
4. App creates required folders.
5. App begins watching for new notes.
6. App processes supported notes automatically.
7. Summaries appear in Obsidian.

---

## 4. Recommended architecture

### Recommended MVP stack

Use a Python-first desktop architecture:

```text
Desktop shell:
  PySide6 or PyQt6

Local backend:
  Python services running inside the same desktop app process

Storage:
  Markdown files inside the Obsidian vault
  SQLite database inside an app metadata folder

File watching:
  watchdog

LLM providers:
  Groq as default online provider
  Provider abstraction for OpenAI, Ollama, and future providers

Document parsing:
  Markdown/text parser
  PDF parser
  DOCX parser
  Image parser with vision model support
  Web clip parser for HTML/text exports

Packaging:
  PyInstaller or Briefcase
```

### Why this stack

Python matches the user's preferred implementation language. PySide6/PyQt6 allows a true desktop app without requiring a separate browser/server deployment. SQLite, Markdown, and local file watching are straightforward in Python. This keeps the app local-first and easier for Codex to implement.

### Alternative later stack

Later, if the UI needs to become more polished, the app can migrate to:

```text
Electron/Tauri frontend
Python backend sidecar
```

But for the MVP, a Python desktop app is simpler and more aligned with the project constraints.

---

## 5. Vault folder structure

When the user selects an Obsidian vault, the app should automatically create:

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

### Folder meanings

#### `LLM Wiki/`

Human-readable generated Markdown files that can be opened directly in Obsidian.

#### `LLM Wiki/Sources/`

One generated summary page per raw source.

Example:

```text
LLM Wiki/Sources/Backpropagation summary.md
```

#### `LLM Wiki/Questions/`

Saved Q&A outputs if the user chooses to preserve useful answers.

#### `LLM Wiki/Flashcards/`

Generated flashcards from processed notes.

#### `LLM Wiki/Active Recall/`

Generated active-recall questions.

#### `LLM Wiki/Audit/`

Human-readable logs of generated changes.

#### `.llm-wiki/`

App-owned metadata folder. This should not be the main place users read content. It is for the app's internal state.

---

## 6. Supported file types

MVP should support all common learning-source formats:

```text
.md
.txt
.pdf
.docx
.html
.htm
.png
.jpg
.jpeg
.webp
```

### Processing expectations

#### Markdown and text

Read directly.

#### PDF

Extract text. Preserve page references when possible.

#### DOCX

Extract paragraphs, headings, tables where feasible.

#### HTML/web clips

Extract readable text and title.

#### Images

Do not skip image support.

If the configured provider supports image processing, use a cheap Groq vision-capable model by default. If unavailable, mark the image as pending and show a clear message that image processing requires a vision-capable model.

The system should store extracted image descriptions as source text in the SQLite index, not as edits to the raw image.

---

## 7. LLM provider requirements

### Default provider

Groq should be the default provider because the product should support open-source model access and relatively inexpensive inference.

### Provider abstraction

Implement a provider interface so models can be swapped later.

Suggested interface:

```python
class LLMProvider:
    def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        ...

    def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        *,
        system: str | None = None
    ) -> str:
        ...

    def supports_vision(self) -> bool:
        ...
```

### Providers to support

MVP:

- Groq

Near-future:

- OpenAI
- Ollama/local models

### Model selection

For non-technical users, do not expose a complex advanced model settings page.

Use app defaults:

```text
Text model:
  best available configured Groq text model

Vision model:
  cheapest configured Groq vision-capable model

Embeddings/indexing:
  local embedding model if feasible, otherwise provider-based embeddings behind the same abstraction
```

If exact model names change, keep them in a config file rather than hardcoding them throughout the app.

---

## 8. Indexing and storage

### SQLite database

Store app state in:

```text
Obsidian Vault/.llm-wiki/app.db
```

### Recommended tables

#### `vaults`

Tracks selected vaults.

```sql
id TEXT PRIMARY KEY
path TEXT NOT NULL
created_at TEXT NOT NULL
last_opened_at TEXT
```

#### `files`

Tracks raw source files.

```sql
id TEXT PRIMARY KEY
vault_id TEXT NOT NULL
path TEXT NOT NULL
relative_path TEXT NOT NULL
file_type TEXT NOT NULL
sha256 TEXT NOT NULL
size_bytes INTEGER
created_at TEXT
modified_at TEXT
last_seen_at TEXT
processing_status TEXT NOT NULL
last_processed_at TEXT
error_message TEXT
```

#### `source_documents`

Stores extracted source text and metadata.

```sql
id TEXT PRIMARY KEY
file_id TEXT NOT NULL
title TEXT
extracted_text TEXT
extraction_metadata_json TEXT
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
```

#### `chunks`

Stores searchable chunks.

```sql
id TEXT PRIMARY KEY
source_document_id TEXT NOT NULL
chunk_index INTEGER NOT NULL
text TEXT NOT NULL
token_count INTEGER
page_number INTEGER
heading TEXT
embedding BLOB
metadata_json TEXT
```

#### `generated_pages`

Tracks LLM-generated Markdown pages.

```sql
id TEXT PRIMARY KEY
source_document_id TEXT
page_type TEXT NOT NULL
path TEXT NOT NULL
relative_path TEXT NOT NULL
sha256 TEXT
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
status TEXT NOT NULL
```

#### `audit_log`

Tracks generated writes.

```sql
id TEXT PRIMARY KEY
event_type TEXT NOT NULL
target_path TEXT
source_paths_json TEXT
summary TEXT NOT NULL
details_json TEXT
created_at TEXT NOT NULL
```

#### `qa_history`

Optional, stores user questions and answers.

```sql
id TEXT PRIMARY KEY
question TEXT NOT NULL
answer TEXT NOT NULL
citations_json TEXT
saved_to_wiki INTEGER NOT NULL DEFAULT 0
created_at TEXT NOT NULL
```

#### `flashcards`

Stores generated flashcards.

```sql
id TEXT PRIMARY KEY
source_document_id TEXT
front TEXT NOT NULL
back TEXT NOT NULL
citation_json TEXT
created_at TEXT NOT NULL
status TEXT NOT NULL
```

#### `active_recall_questions`

Stores generated active-recall questions.

```sql
id TEXT PRIMARY KEY
source_document_id TEXT
question TEXT NOT NULL
expected_answer TEXT
difficulty TEXT
citation_json TEXT
created_at TEXT NOT NULL
status TEXT NOT NULL
```

---

## 9. File watching behavior

Use `watchdog` to monitor the selected Obsidian vault.

### Default behavior

Existing personal notes are treated as raw sources by default.

The app should monitor the vault for new or changed files.

### Exclude app-owned folders

The watcher must ignore:

```text
LLM Wiki/
.llm-wiki/
.obsidian/
.trash/
.git/
```

This avoids reprocessing generated files and Obsidian metadata.

### Hash-based processing

A raw source file should be reprocessed only if its hash changes.

Use SHA-256.

### Automatic processing

The app should process new notes automatically when they appear.

Recommended behavior:

1. File watcher detects new or changed supported file.
2. App waits briefly for file write to finish.
3. App computes hash.
4. If new hash, app queues extraction.
5. App extracts text.
6. App chunks/indexes content.
7. App asks LLM to generate source summary, flashcards, and active recall.
8. App writes Markdown files into `LLM Wiki/`.
9. App updates generated page records and processing logs.

---

## 10. Automatic write workflow

The app writes generated content automatically into app-owned folders.

Safety comes from:

- never modifying raw notes
- writing only inside `LLM Wiki/` and `.llm-wiki/`
- excluding generated folders from ingestion
- logging every generated write

Examples:

```text
Generated new file:
  LLM Wiki/Sources/Backpropagation summary.md

Generated new file:
  LLM Wiki/Flashcards/Backpropagation flashcards.md

Generated new file:
  LLM Wiki/Active Recall/Backpropagation questions.md
```

The app should still let the user inspect generated files after write, including:

- Target file path
- Source file path
- Generated Markdown preview
- Citations/source references
- Processing time
- Error state if generation failed

Generated files are written to disk and recorded in the audit log immediately after successful processing.

---

## 11. Generated Markdown templates

### Source summary page

Path:

```text
LLM Wiki/Sources/{source_title} summary.md
```

Template:

```markdown
# {Source Title} Summary

Source: [[{relative_source_path_or_title}]]
Generated: {timestamp}
Status: LLM-generated

## Overview

{short high-level summary}

## Key Ideas

- {idea 1}
- {idea 2}
- {idea 3}

## Important Details

{structured explanation of the source}

## Terms and Definitions

- **Term:** definition

## Connections

Related generated pages:

- [[Another Source Summary]]

## Questions This Source Helps Answer

- {question 1}
- {question 2}

## Source-Grounded Notes

{notes with page/section references when available}

## Citations

- `{relative_source_path}`, section/page/chunk: {reference}
```

### Flashcards page

Path:

```text
LLM Wiki/Flashcards/{source_title} flashcards.md
```

Template:

```markdown
# {Source Title} Flashcards

Source: [[{source_summary_page}]]

## Flashcards

### Card 1

Front: {question}

Back: {answer}

Citation: `{relative_source_path}`, {reference}

---

### Card 2

Front: {question}

Back: {answer}

Citation: `{relative_source_path}`, {reference}
```

### Active recall page

Path:

```text
LLM Wiki/Active Recall/{source_title} questions.md
```

Template:

```markdown
# {Source Title} Active Recall

Source: [[{source_summary_page}]]

## Questions

### 1. {question}

Expected answer:

{answer}

Citation: `{relative_source_path}`, {reference}
```

### Index page

Path:

```text
LLM Wiki/_Index.md
```

Template:

```markdown
# LLM Wiki Index

This folder is generated by the Local LLM Wiki app.

## Source Summaries

{auto-generated list of links}

## Flashcards

{auto-generated list of links}

## Active Recall

{auto-generated list of links}

## Recent Processing

See [[_Processing Log]].
```

### Processing log

Path:

```text
LLM Wiki/_Processing Log.md
```

Append entries like:

```markdown
## {timestamp}

Processed source: `{relative_source_path}`

Generated:

- [[{summary_page}]]
- [[{flashcards_page}]]
- [[{active_recall_page}]]

Status: Auto-generated
```

---

## 12. Q&A behavior

The app should support asking questions over the user's processed notes.

### Recommended retrieval flow

1. User asks a question.
2. Search generated source summaries first.
3. Search raw source chunks second.
4. Build a grounded prompt with citations.
5. Generate an answer.
6. Show answer with cited source files and generated wiki pages.
7. Let user save useful answer to `LLM Wiki/Questions/`.

### Citation policy

Answers should cite both when available:

- Generated wiki summary pages
- Raw source files/chunks

Raw sources remain the ultimate source of truth.

### Saved answer template

```markdown
# {Question Title}

Question: {original question}
Asked: {timestamp}

## Answer

{answer}

## Sources

- [[{source_summary_page}]]
- `{relative_raw_source_path}`, {reference}
```

---

## 13. Karpathy-inspired behavior to preserve

The core idea to preserve is the separation between:

1. Raw sources
2. Generated wiki
3. App instructions/schema/index

### Raw sources

User-authored or imported material. Immutable.

### Generated wiki

LLM-created Markdown pages. User-inspectable and editable.

### Instructions/schema/index

Rules and metadata the app uses to maintain consistency.

For MVP, the generated wiki should be intentionally narrow:

- One summary per source
- Flashcards per source
- Active recall per source
- Index/log pages

Later versions can add concept pages, topic maps, contradiction tracking, and automatic page updates across related generated pages.

---

## 14. Git integration

Include Git integration in MVP if feasible, but keep it simple.

### Goals

- Track generated wiki changes.
- Help users inspect history.
- Provide safety without implementing a custom rollback button.

### Behavior

If the selected vault is already a Git repository:

- Commit generated changes with a clear message.

If not:

- Offer to initialize Git in the vault.
- Do not force Git setup.

### Commit message format

```text
llm-wiki: add summary for {source_title}
```

### Do not commit raw user notes unless already tracked

The app should not unexpectedly add all raw notes to Git. For safety, commit only generated files and app-owned audit files unless the user has existing Git behavior.

---

## 15. Audit logging

Every generated write must be logged.

Write audit logs in both SQLite and a human-readable file.

Recommended file:

```text
LLM Wiki/Audit/audit-log.jsonl
```

Each line:

```json
{
  "timestamp": "2026-04-29T10:00:00Z",
  "event_type": "generated_summary_written",
  "source_path": "Raw/Backpropagation.md",
  "generated_paths": [
    "LLM Wiki/Sources/Backpropagation summary.md",
    "LLM Wiki/Flashcards/Backpropagation flashcards.md",
    "LLM Wiki/Active Recall/Backpropagation questions.md"
  ],
  "model_provider": "groq",
  "model": "configured-default",
  "content_hash": "..."
}
```

Also append a readable entry to:

```text
LLM Wiki/_Processing Log.md
```

---

## 16. UI requirements

### First-run wizard

Screens:

1. Welcome
2. Select Obsidian vault folder
3. Confirm folders to be created
4. Configure Groq API key
5. Test provider connection
6. Start indexing

### Main app sections

#### Dashboard

Show:

- Selected vault
- Number of raw sources found
- Number processed
- Number queued or processing
- Last processing time
- Provider status

#### Processing Activity

Show recent generated files, processing status, and errors.

Suggested details:

- Latest generated file path
- Source file path
- Status
- Timestamp
- Error message when applicable

#### Sources

List indexed raw sources with processing status.

#### LLM Wiki

List generated summary, flashcard, and active-recall files.

#### Ask

Q&A interface over processed material.

#### Settings

Keep settings minimal:

- Vault path
- Provider API key
- Provider connection status
- Enable/disable automatic processing
- Enable/disable Git integration

Do not expose advanced model, temperature, chunk size, or prompt controls to ordinary users in MVP.

---

## 17. Security and privacy

### Local storage

Store all vault data locally.

### API keys

Store API keys securely using OS keychain if possible.

Use:

```text
keyring
```

for Python credential storage.

Fallback to encrypted local config only if keychain is unavailable.

### LLM privacy warning

The app should clearly explain:

- Notes stay on the user's machine.
- Text/images selected for processing may be sent to the configured LLM provider.
- Raw notes are never modified.
- Generated summaries are written automatically into app-owned folders.

### No multi-user cloud requirement

Because this is a local desktop app, user separation is handled by the operating system and by each user's local vault.

There is no Clerk authentication requirement for MVP.

---

## 18. Implementation modules

Suggested Python package structure:

```text
llm_wiki/
  app.py
  ui/
    main_window.py
    wizard.py
    dashboard.py
    activity.py
    ask.py
    settings.py
  core/
    config.py
    vault.py
    watcher.py
    hashing.py
    database.py
    audit.py
    git.py
  ingestion/
    router.py
    markdown.py
    text.py
    pdf.py
    docx.py
    html.py
    image.py
    chunking.py
  llm/
    base.py
    groq_provider.py
    openai_provider.py
    ollama_provider.py
    prompts.py
  wiki/
    paths.py
    templates.py
    generator.py
    writer.py
    index_page.py
  retrieval/
    search.py
    embeddings.py
    qa.py
  tests/
    test_hashing.py
    test_vault.py
    test_templates.py
    test_ingestion.py
    test_generated_pages.py
```

---

## 19. Core implementation flow

### App startup

1. Load config.
2. If no vault configured, show first-run wizard.
3. Open SQLite database.
4. Ensure required folders exist.
5. Scan vault for supported files.
6. Ignore app-owned folders.
7. Add new/changed files to processing queue.
8. Start file watcher.

### New file processing

```text
File detected
→ wait for stable write
→ compute hash
→ check DB
→ extract text or image description
→ chunk content
→ store source/chunks
→ call LLM for summary
→ call LLM for flashcards
→ call LLM for active recall
→ write Markdown file(s)
→ update generated_pages
→ update _Index and _Processing Log
→ write audit-log.jsonl
→ optionally commit generated files to Git
→ notify user
```

### Automatic generated content write

```text
Generation succeeds
→ write Markdown file(s)
→ update generated_pages
→ update _Index.md
→ update _Processing Log.md
→ write audit-log.jsonl
→ optionally commit generated files to Git
```

---

## 20. Prompt requirements

### System prompt for source summary generation

The source-summary prompt should say:

```text
You are maintaining a local, Obsidian-compatible LLM Wiki for a learner.

Rules:
- Do not invent facts.
- Use only the provided source content.
- Preserve source grounding.
- Write in clear Markdown.
- Use Obsidian [[Wiki Links]] when referring to generated pages or important concepts.
- This is a generated source summary, not an edit to the raw source.
- Focus on helping the user learn the material.
- Include key ideas, definitions, examples, and questions the source helps answer.
- If the source is unclear or incomplete, say so.
```

### Flashcard prompt

```text
Generate concise learning flashcards from the source.
Each flashcard must be answerable from the source.
Avoid trivia.
Prefer conceptual understanding.
Include citation references.
```

### Active recall prompt

```text
Generate active-recall questions that help the learner test understanding.
Include expected answers.
Prefer questions that reveal whether the learner understands the core ideas.
Include citation references.
```

### Q&A prompt

```text
Answer the user's question using only the retrieved wiki pages and raw source chunks.
Cite sources.
If the answer is not supported by the sources, say so.
Prefer generated wiki summaries first, but use raw sources as the source of truth.
```

---

## 21. MVP acceptance criteria

The MVP is successful when:

1. A non-technical user can install and open the desktop app.
2. The user can select an existing Obsidian vault.
3. The app automatically creates `LLM Wiki/` and `.llm-wiki/`.
4. Existing notes are discovered as raw sources by default.
5. Generated/app-owned folders are excluded from raw-source processing.
6. The app detects new or changed supported files.
7. The app processes Markdown, text, PDF, DOCX, HTML, and image files.
8. The app generates one source-summary Markdown page per source.
9. The app generates flashcards and active-recall questions per source.
10. Generated files are written automatically inside app-owned vault folders.
11. Users can inspect generated files and their citations after processing.
12. Raw notes are never modified.
13. Obsidian can open and navigate the generated Markdown.
14. The app tracks processed files by hash.
15. The app maintains a SQLite index.
16. The app maintains a human-readable audit log.
17. The app can answer questions over processed notes with citations.
18. Git integration can commit generated changes if enabled.
19. Groq works as the default LLM provider.
20. Provider abstraction exists for future OpenAI/Ollama support.

---

## 22. Explicit non-goals for MVP

Do not build these in MVP:

- Cloud sync
- Clerk authentication
- Multi-user web accounts
- Vercel/Netlify deployment
- Automatic concept pages
- Automatic topic maps
- Automatic updates across all generated concept pages
- Editing raw user notes
- Rollback button
- Advanced prompt/model settings UI
- Full Obsidian plugin
- Mobile app

---

## 23. Future roadmap

### Version 0.2

- Concept pages
- Topic pages
- Learning maps
- Contradiction detection
- Update relevant generated pages when new sources arrive
- Smarter backlinks
- Better spaced repetition

### Version 0.3

- Obsidian plugin companion
- Local model support with Ollama
- Better offline mode
- Semantic graph visualization
- Importers for browser bookmarks, email exports, and transcripts

### Version 1.0

- Fully packaged non-technical desktop installer
- Robust provider management
- Polished generation activity UX
- Strong local privacy controls
- Optional sync between multiple machines

---

## 24. Codex implementation instruction

Implement this project incrementally.

Start with the local desktop app skeleton, vault selection, folder creation, SQLite schema, file scanning, and hash-based indexing.

Then implement Markdown/text ingestion and one generated source-summary write.

Only after that, add PDF/DOCX/HTML/image ingestion, flashcards, active recall, Q&A, Git integration, and packaging.

Prioritize safety:
- Never edit raw notes.
- Never process generated folders as raw sources.
- Never write generated content outside app-owned folders.
- Always log generated writes.

