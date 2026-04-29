# Auto-Write Safety

## Decision

The MVP auto-writes generated content instead of asking for pre-write approval.

## Why

- lower friction
- simpler workflow
- faster path to usable Obsidian output

## What Must Replace Manual Review

- strict path ownership checks
- generated-folder exclusions
- bounded retries
- explicit processing states
- audit logs
- post-write inspection UI

## Required Safeguards

1. Never write outside `LLM Wiki/` or `.llm-wiki/`.
2. Use atomic writes.
3. Fail closed on unsafe paths.
4. Label generated files clearly in content and UI.
5. Keep raw citations visible.
