# Local LLM Wiki for Obsidian — Project Description & Implementation Plan

## 1. Product summary

Build a local-first app that connects to an existing Obsidian vault, watches a dedicated Raw/ folder, and maintains a concise, editable, interlinked Wiki/ folder inside the same vault.

The product is not a classic RAG app. The important idea is that raw documents are not searched from scratch every time. Instead, the LLM reads raw sources, compiles them into a persistent Markdown wiki, updates the wiki over time, and uses that compiled wiki first when answering questions. This as a persistent, compounding artifact that gets richer with every source and every question.

The first platform is a desktop app. Android comes in v2, but the repository should be structured from day one so Android can share concepts, schema, prompts, and page rules.


---

## 2. Core product goals

The product should help the user turn personal learning material into a clean, source-grounded wiki. It should do it by turning messy or scattered Obsidian notes into an organized, source-grounded LLM wiki

### Primary Goals:
1. Convert raw inputs into structured knowledge.
2. Create concise concept/entity/comparison/map pages.
3. Update multiple wiki pages from one source.
4. Maintain links between related ideas.
5. Use the compiled wiki first during Ask.
6. Use raw sources only for verification/citation when needed.
7. Run lint/maintenance automatically.
8. Keep raw files immutable.
9. Keep generated Markdown editable and persistent.
10. Keep the implementation simple, clean, and high quality.

The ingest flow explicitly includes reading a source, writing wiki material, updating the index, updating relevant entity/concept pages, and appending to the log; he notes that one source can touch many wiki pages.

---

## 3. Core Product Decisions
```text
Visible vault folders:
  Raw/
  Wiki/

Hidden app folder:
  .llm-wiki/

Desktop stack:
  Electron + React frontend
  Python backend

Android v2:
  Expo / React Native if practical
  Same product behavior as desktop
  Direct access to same local Android vault folder where possible

LLM:
  Groq API

Default indexing:
  SQLite FTS5 first
  No vector DB in MVP

Obsidian integration:
  Use Obsidian-compatible Markdown and [[Wiki Links]]
  Use official Obsidian CLI where it helps. The obsidian cli commands are mentioned in OBSIDIAN_CLI_COMMANDS.md file.
  Do not depend on Obsidian CLI for core file writes

Ask:
  Keep Ask section
  Instant answers only
  Do not save Ask answers automatically

Review:
  New pages can be created automatically
  Updates to existing pages require review first
  User can approve one page or approve all

Images:
  Detect image files
  Mark pending for now
  Do not process images in MVP
```

The official Obsidian CLI is useful for read/search/write automation, but it requires Obsidian to be running; therefore, core writes should be direct atomic filesystem writes, while Obsidian CLI should be an optional adapter for opening/searching/diffing with Obsidian when available.

---

## 4. Three layer architecture
```text
Raw Layer
  Raw source files.
  Immutable.
  User-curated.
  Never edited by the app.

Wiki Layer
  LLM-maintained Markdown pages.
  Editable by the user.
  Short, structured, source-cited, interlinked.

Schema Layer
  Hidden rules, prompts, templates, and constraints.
  Stored in .llm-wiki/.
  Used by the app/LLM to keep behavior consistent.
```
Karpathy’s architecture separates raw sources, wiki, and schema/instructions; raw sources are the source of truth, and the LLM maintains the wiki layer

---

## 5. Vault Folder Structure
```text

Obsidian Vault/
  Raw/
    PDFs/
    Notes/
    Code/
    Web/
    Images/
    Other/

  Wiki/
    index.md
    log.md

    Concepts/
    Entities/
    Comparisons/
    Maps/
    Flashcards/
    Reviews/

  .llm-wiki/
    app.db
    config.json
    schema.json
    audit.jsonl

    prompts/
      core.md
      ingest.md
      query.md
      lint.md
      flashcards.md

    cache/
      extractions/
      proposed-updates/
      file-hashes/
```

The raw file itself is the source. Extracted text, chunk metadata, and citation anchors live in SQLite/cache, not in visible wiki pages.

## 6. Page Types

```text
Concept
  Short explanation of an idea.

Entity
  Person, tool, framework, organization, project, method, model, etc.

Comparison
  X vs Y, tradeoffs, differences, similarities.

Map
  Learning map, topic outline, dependency map.

Flashcards
  Per source or per concept.

Review
  Contradictions, stale claims, uncertain claims, low-confidence concepts.
```

## 7. Page Style
Pages should be concise. The LLM may choose the internal structure, but each page must stay short, readable, linked, and cited.

Recommended soft limits:
```text
Concept page:
  150–350 words

Entity page:
  100–300 words

Comparison page:
  Short table + 3–6 notes

Map page:
  Outline format

Flashcard page:
  Compact Q/A cards

Review page:
  One issue cluster per page
```

When a page becomes too large, the app should propose a split instead of automatically rewriting the whole structure. This is safer and more token-efficient.

## 8. Index and navigation
`Wiki/index.md` is the human-readable navigation layer. It should list important wiki pages with a one-line summary and category grouping.

Example:
```md
# Simple Wiki Index

## Concepts

- [[Attention Mechanism]] — How models focus on relevant parts of input.
- [[Backpropagation]] — How gradients are propagated through a model.

## Entities

- [[Andrej Karpathy]] — AI researcher associated with neural networks, Tesla AI, and LLM Wiki idea.

## Comparisons

- [[RAG vs LLM Wiki]] — Difference between retrieval-time synthesis and compiled persistent knowledge.

## Maps

- [[Neural Networks Learning Map]] — Suggested path through neural network concepts.
```

`index.md` is catalog of wiki pages with links and one line summary. The LLM reads it first and drills into relevant pages. At larger scale, a searchable index can replace reading the whole file each time, which matches the SQLite FTS5 plan

### Implementation Principles
```text
Human-facing retrieval:
  Wiki/index.md → wiki pages → raw verification

Actual app retrieval:
  SQLite FTS5 mirror of Wiki/index.md + Wiki/*.md
  Then load relevant pages and graph neighbors
  Then raw chunks only if needed
```

## 9. Schema and prompts
Use hidden schema/config in .llm-wiki/, not a visible schema.md in the wiki.

Recommended files:
```text
.llm-wiki/schema.json
.llm-wiki/prompts/core.md
.llm-wiki/prompts/ingest.md
.llm-wiki/prompts/query.md
.llm-wiki/prompts/lint.md
.llm-wiki/prompts/flashcards.md
```

A more token-efficient pattern is to keep only core rules always loaded and split operation-specific logic into separate ingest/lint/query prompt files.

`core.md` should contain only durable rules
```text
- Never modify Raw/.
- Write only inside Wiki/ and .llm-wiki/.
- Keep pages concise.
- Use Obsidian [[Wiki Links]].
- Cite sources for claims.
- Update index.md and log.md after meaningful ingest/update events.
- Use compiled wiki knowledge first.
- Use raw sources only for verification and grounding.
- Do not create duplicate concept pages.
- Prefer updating existing pages over creating near-duplicates.
```

## 10. Ingest Workflow
The ingest workflow is the heart of the product.

1. User drops files into Raw/.
2. App detects new/changed file.
3. App waits for stable write.
4. App computes SHA-256 hash.
5. App checks SQLite state.
6. App extracts text.
7. If file is image, mark pending.
8. Store extraction/chunks/citation anchors in SQLite FTS5.
9. LLM identifies:
   - concepts
   - entities
   - comparisons
   - possible maps
   - flashcard opportunities
   - contradictions or uncertainty
10. App creates new wiki pages automatically.
11. App prepares diffs for existing page updates.
12. User reviews proposed diffs.
13. User approves individually or approves all.
14. App writes approved changes.
15. App updates index.md.
16. App appends meaningful event to log.md.
17. App generates flashcards.
18. App runs lint.
19. App auto-fixes safe broken mechanical issues.
20. App creates Review pages for semantic issues.
21. App records audit.jsonl.
22. If Git is enabled, app commits.

The key rule is: new source data should update the existing knowledge graph, not merely append a new summary page.

## 11. Review before update behavior

New Pages:
- Create immediately
- No approval required

Existing Pages:
- Generate proposed diff.
- Show current page vs proposed page.
- User can approve, reject, or approve all.
- Only approved updates are written.

This gives the system the ability to compound knowledge while protecting existing notes from unnecessary churn.

## 12. Low Confidence Behavior
For low-confidence concepts, contradictions, or unclear claims:
- Do not create weak stub concept pages.
- Create a short Review page instead.

### Example

`Wiki/Reviews/Unclear claim from backpropagation paper.md`

Review page template:
```markdown
# Review: Unclear claim from {source}

## Issue

The source appears to suggest {claim}, but confidence is low.

## Why this needs review

- The wording is ambiguous.
- The claim may conflict with [[Existing Concept]].

## Source

- `Raw/PDFs/example.pdf`, page 7

## Suggested next step

Check the source manually or add another source.
```
This is safer than filling the wiki with low-quality stubs.

## 13. Ask workflow
Ask remains in the app, but it is instant only and does not save answers automatically.

User asks question
1. Search Wiki/index.md mirror using SQLite FTS5
2. Load relevant wiki pages
3. Load linked neighbor pages if useful
4. Use raw chunks only for verification/citations
5. Generate concise answer with citations
6. Show answer

Buttons:
- Copy
- Open cited wiki page
- Open cited raw source
- Propose wiki update
- Generate flashcards from answer

Do not create Wiki/Questions/. Do not automatically write Ask outputs into the wiki.

Query answers can become new wiki artifacts, but in this product that should be manual through “Propose wiki update,” because you explicitly prefer Ask to be instant and not saved by default.

## 14. Lint and Maintenance 
Lint runs automatically after each ingest.

Auto-fix only safe mechanical issues:
- Missing index entries
- Broken index links when target is obvious
- Missing backlinks where target is obvious
- Empty duplicate pages
- Broken internal links caused by known rename/path issue

Create review pages for semantic issues
- Contradictions
- Stale claims
- Uncited claims
- Duplicate concepts that require judgment
- Overlong pages
- Low-confidence extracted concepts
- Orphan pages that may or may not belong

There is strong emphasize on lint, contradiction detection, stale-claim detection, broken links, health tools, and citation validation; one discussion specifically mentions typed graphs as a clean place to flag contradictions and stale claims

## 15. Citation Policy

Every generated claim should cite a source when practical.

Citation format:
```md
This concept means X and is used for Y.  
Source: `Raw/PDFs/example.pdf`, p. 4
```

For non-PDF files:
```md
Source: `Raw/Notes/example.md`, section "Gradient Descent"
Source: `Raw/Web/article.html`, paragraph 12
Source: `Raw/Code/example.py`, lines 20–45
```

SQLite stores citation anchors:
```text
source_file
page_number
section_heading
paragraph_index
line_start
line_end
chunk_id
```

## 16. Flashcards
Generate flashcards from:
1. Raw source extraction
2. Concept pages

Store as markdown
- Wiki/Flashcards/{concept-or-source-title}.md

Templates:
```md
# Flashcards: {Title}

## Cards

### 1. {Question}

{Answer}

Source: `Raw/...`, p. X

---

### 2. {Question}

{Answer}

Source: [[Concept Page]], `Raw/...`, section Y
```

## 17. File type support
```text
.md
.txt
.pdf
.docx
.html
.htm
.py
.js
.ts
.java
cpp/c/cs/go/rs/etc.
.csv
.json
.yaml
.png
.jpg
.jpeg
.webp
```

Processing behavior:
```text
Markdown/TXT:
  Extract directly.

PDF:
  Extract text with page references.

DOCX:
  Extract paragraphs, headings, tables.

HTML:
  Extract readable title/body.

Code:
  Treat as learning material if placed in Raw/.

Images:
  Detect and mark pending.
  Do not process content yet.
```

## 18. SQLite and search
Use SQLite as the local app state and FTS5 search layer.

Recommended tables:
```text
vaults
files
extractions
chunks
wiki_pages
wiki_links
proposed_updates
audit_events
flashcards
review_items
ask_history_ephemeral
```

FTS5 virtual tables:
```
wiki_pages_fts
chunks_fts
index_fts
```

Important rule:
- Wiki FTS is primary for Ask.
- Raw chunk FTS is secondary for verification.

## 19. Git and audit

Git should be optional but strongly recommended during setup.

Why: the wiki is Markdown files, and Git gives version history and rollback. Karpathy notes that a wiki can simply be a Git repo of Markdown files, giving version history, branching, and collaboration.

Behavior:

- If vault is already a Git repo:
  - Offer to commit Wiki/ and .llm-wiki/audit.jsonl changes.

- If vault is not a Git repo:
  - Offer to initialize Git.
  - Do not force it.

- Do not commit app.db by default.
- Do not commit cache files by default.
- Do not add Raw/ unless user explicitly wants it.

Commit examples:
```text
checkpoint: before ingest backpropagation-paper
ingest: backpropagation-paper
lint: repair wiki index links
flashcards: attention mechanism
review: contradiction in transformer notes
```

Always write .llm-wiki/audit.jsonl, even if Git is disabled.

## 20. Obsidian Integration

Use direct filesystem writes for generated Markdown because it is simpler, reliable, and does not require Obsidian to be running.
Use Obsidian CLI optionally for:
- opening a generated note
- searching the vault through Obsidian
- diffing files
- reading active/current note
- future Obsidian-specific automation
- finding connections b/w

The official CLI supports reading, searching, creating, appending, diffing, and other vault actions, but the app must be running for CLI use.

Therefore the core app works if Obsidian is closed. The obsidian cli features work only if obsidian is available and running

## 21. Desktop Architecture
Use:
- Electron + React frontend
- Python FastAPI backend
- SQLite local database
- Watchdog file watcher
- Groq provider
- Direct Markdown writer
- Optional Obsidian CLI adapter
- Optional Git adapter

Electron is appropriate because it gives a cross-platform desktop shell using web technologies and runs on macOS, Windows, and Linux.

Recommended process model:
```text
Electron main process
  starts bundled Python backend as child process

Python backend
  exposes local FastAPI HTTP API
  exposes WebSocket/SSE event stream for progress updates
  performs ingestion, LLM calls, indexing, lint, writes

React frontend
  calls local backend
  shows dashboard, diffs, Ask, settings
```

This is cleaner than doing long-running ingestion in Electron. Existing Electron/Python patterns commonly spawn a Python backend process and communicate through local messaging or API boundaries.

Backend should run only while the desktop app is open in MVP. A tray/background service can come later.

## 22. Android v2 Architecture

Android should have the same app behavior as desktop:
```text
Select vault folder
Watch/access Raw/
Process files
Call Groq
Write Wiki/
Show diffs
Run Ask
Run lint
Generate flashcards
```
Use Expo/React Native if practical. Expo is a React Native framework for building native apps, and Expo FileSystem provides access to local files/directories on Android and iOS

Some important android notes
- Do not depend on Obsidian CLI on Android.
- Use Android folder access / storage access flow.
- Write Markdown directly to the vault folder if permissions allow.

If Python is practical on Android, share more backend logic. If not, reimplement the core operations in TypeScript while sharing schema/prompt definitions.

## 23. Repository Structure
```text
simple-wiki/
  apps/
    desktop/
      electron/
        src/
        package.json
      backend/
        simple_wiki/
          api/
          core/
          ingestion/
          llm/
          wiki/
          retrieval/
          lint/
          git/
          obsidian/
          db/
        pyproject.toml

    android/
      app/
        package.json
        src/
      README.md

  packages/
    shared/
      schema/
        page-types.json
        config.schema.json
        audit-event.schema.json
      prompts/
        core.md
        ingest.md
        query.md
        lint.md
        flashcards.md
      markdown/
        templates/

  docs/
    product-plan.md
    architecture.md
    acceptance-criteria.md
    prompts.md

  tests/
    fixtures/
      raw/
      wiki/
      
```

## Main app screens
```text
Welcome / Setup
  Select vault
  Create Raw/, Wiki/, .llm-wiki/
  Add Groq API key
  Test Groq
  Recommend Git

Dashboard
  Vault path
  Raw file count
  Processed count
  Pending reviews
  Pending images
  Last ingest
  Lint health

Raw Inbox
  Files in Raw/
  Status: new / processing / processed / pending image / error

Proposed Updates
  Diff viewer
  Approve one
  Approve all
  Reject
  Open in Obsidian

Wiki Browser
  Concepts
  Entities
  Comparisons
  Maps
  Flashcards
  Reviews

Ask
  Instant answer
  Wiki-first citations
  Raw verification citations
  Copy
  Propose wiki update

Lint
  Auto-fixed issues
  Review-needed issues

Settings
  Vault path
  Groq key
  Model IDs
  Git enabled
  Obsidian CLI status
  Auto-processing on/off
```

## 25. Groq model config
Used fixed model IDs in config. dont auto-fetch
Recommended default:
```json

{
  "provider": "groq",
  "default_text_model": "openai/gpt-oss-120b",
  "cheap_fast_model": "llama-3.1-8b-instant",
  "review_model": "openai/gpt-oss-120b",
  "vision_model": null
}
```

## 26. Security and privacy
- Vault stays local.
- Raw files stay local.
- Extracted text is sent to Groq for processing.
- Images are not sent in MVP.
- API key stored in OS keychain where available.
- Fallback: encrypted local config.
- Raw/ is never modified.
- Wiki/ is editable.
- .llm-wiki/app.db is local only.

Show this warning during the setup:
Your files stay in your Obsidian vault. To generate wiki pages, the app extracts text from files in Raw/ and sends that extracted text to Groq through the Groq API. Raw files are never edited by the app.

## 27. Acceptance Criteria
Implementation is successful when:

1. User installs desktop app and
2. User selects existing Obsidian vault.
3. App creates Raw/, Wiki/, .llm-wiki/.
4. User drops files into Raw/.
5. App processes all required non-image file types.
6. Images are detected and marked pending.
7. App never edits Raw/.
8. App creates concise Concept pages.
9. App creates concise Entity pages.
10. App creates concise Comparison pages.
11. App creates concise Map pages.
12. App generates Flashcards.
13. One raw source can update multiple wiki pages.
14. New pages are created automatically.
15. Existing page updates require review.
16. User can approve one update or all updates.
17. Every generated claim has a source citation when practical.
18. index.md is updated after ingest.
19. log.md records meaningful ingest/update events.
20. SQLite FTS5 indexes wiki pages and raw chunks.
21. Ask uses wiki pages first.
22. Ask uses raw chunks only for verification/citations.
23. Ask answers are not saved automatically.
24. Lint runs automatically after ingest.
25. Lint auto-fixes safe broken mechanical issues.
26. Lint creates Review pages for semantic issues.
27. Optional Git can checkpoint and commit wiki changes.
28. Obsidian can navigate the generated wiki normally.
29. Obsidian CLI is optional and hidden behind the app.
30. Groq works as the default model provider.