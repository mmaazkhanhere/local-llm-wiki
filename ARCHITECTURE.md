# Architecture

## System Shape

The MVP is a single desktop application with local services and filesystem integration.

Primary layers:

1. UI layer
2. core application services
3. ingestion pipeline
4. LLM provider abstraction
5. wiki generation and writing
6. retrieval and Q&A
7. audit and reliability support

## High-Level Flow

```text
Vault selected
-> required folders created
-> initial scan indexes supported raw files
-> watcher monitors vault
-> changed file is debounced and hashed
-> extractor converts file to normalized source text
-> chunker creates retrieval units
-> provider generates summary and learning artifacts
-> writer stores Markdown in LLM Wiki/
-> generated_pages and audit_log updated
-> UI shows processing status and generated outputs
```

## Modules

Suggested package layout:

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
    retries.py
    errors.py
  ingestion/
    router.py
    markdown.py
    text.py
    pdf.py
    docx.py
    html.py
    image.py
    chunking.py
    titles.py
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
    qa.py
  tests/
```

## Core Boundaries

### Core Services

Responsibilities:

- load config
- open database
- enforce path ownership
- manage watcher lifecycle
- schedule and serialize processing jobs

### Ingestion

Responsibilities:

- route by file type
- extract normalized text
- attach metadata such as title, page references, and extraction method
- emit chunkable content

### LLM Boundary

Provider-specific code must stay behind a narrow interface.

Minimum interface:

- `generate_text(prompt, system_prompt, metadata)`
- `generate_with_image(prompt, image_path, system_prompt, metadata)`
- `supports_vision()`
- `provider_name()`

Later interface additions:

- `embed_text(texts)`
- `supports_embeddings()`

The rest of the app must not know provider request payload details or response schemas.

### Wiki Writer

Responsibilities:

- resolve safe app-owned output paths
- apply filename normalization
- write Markdown atomically
- update `_Index.md`
- update `_Processing Log.md`
- record `generated_pages`

### Retrieval

First pass is lexical or text-based retrieval only.

Scope for MVP:

- search generated summaries first
- search raw chunks second
- build grounded prompt from matching chunks
- answer only from retrieved evidence

Embeddings are deferred.

## Architecture Decisions

### Auto-Write Instead of Review Queue

This repo no longer uses a pre-write approval queue.

That means safety must come from:

- strict write-scope enforcement
- strong watcher exclusions
- source-grounded prompts
- explicit status tracking
- audit logs for every generated write

### One Summary Per Source

The MVP generates one summary page per raw source.

This avoids:

- concept-page invalidation logic
- cross-document synchronization
- aggressive backlink orchestration
- complex regeneration dependency graphs

### SQLite as Source of App State

SQLite holds:

- file hashes and status
- extracted content metadata
- chunks
- generated page records
- audit records
- optional Q&A history later
