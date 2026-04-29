# AGENTS.md

## Purpose

This repository defines a local-first desktop app that builds an LLM-maintained wiki inside an existing Obsidian vault.

Agent work in this repo must preserve the following non-negotiable constraints:

- Never edit, move, rename, or delete raw user notes.
- Never process files inside `LLM Wiki/` as raw inputs.
- Never process files inside `.llm-wiki/` as raw inputs.
- Never write generated content outside app-owned folders.
- Always record generated writes in both SQLite and a human-readable audit log.
- Prefer readable Markdown outputs that remain fully usable inside Obsidian.

## Current Product Direction

The current MVP direction is:

- desktop app, not web app
- Python-first architecture
- auto-write generated content into app-owned folders
- no pre-write approval step
- post-write inspection and auditability
- Groq as default provider
- OpenAI and Ollama reserved for provider abstraction
- simple text retrieval for first Q&A pass
- embeddings are not required for first-pass Q&A

## Folder Ownership

Raw source area:

- everything in the selected vault except excluded folders

Generated and app-owned areas:

- `LLM Wiki/`
- `.llm-wiki/`

Watcher exclusions:

- `LLM Wiki/`
- `.llm-wiki/`
- `.obsidian/`
- `.git/`
- `.trash/`

## Filename Rules

Generated filenames must be readable, deterministic, and safe on Windows.

Rule set:

1. Start from extracted title if available, else raw file stem.
2. Trim surrounding whitespace.
3. Replace forbidden filename characters `< > : " / \ | ? *` with ` - `.
4. Remove control characters and trailing dots/spaces.
5. Collapse repeated whitespace to one space.
6. Keep the readable title casing instead of slugifying everything.
7. Limit the base name to 120 characters.
8. Append suffixes by page type:
   - summary: ` summary.md`
   - flashcards: ` flashcards.md`
   - active recall: ` questions.md`
9. On collision, append ` ({short_hash})` before `.md`.

Example:

- raw title: `Backpropagation: Notes / v2`
- summary file: `Backpropagation - Notes - v2 summary.md`

## Delivery Expectations

When creating implementation work:

- prefer small, testable slices
- land safety-critical infrastructure before richer features
- keep provider-specific logic behind a narrow interface
- keep docs and implementation aligned
