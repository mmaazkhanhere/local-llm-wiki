# Architecture

This file is an entry point. Canonical architecture docs live in `docs/`.

## System of Record (Read Order)

1. `docs/design-docs/index.md`
2. `docs/generated/db-schema.md`
3. `IMPLEMENTATION_PLAN.md`

## Current Direction (MVP)

- local-first Electron desktop app: `apps/desktop/electron`
- compile raw sources into a persistent, Obsidian-readable markdown wiki
- enforce a hard boundary between:
  - raw notes (source of truth; never modified)
  - generated wiki output (app-owned)
  - hidden app state (app-owned index/audit/status)
- auto-writes are allowed only within app-owned folders; write-scope + auditability are mandatory (`docs/design-docs/auto-write-safety.md`)
- retrieval stays simple/lexical until it is measurably insufficient (`docs/design-docs/retrieval-strategy.md`)

## Change Rule

If architecture or invariants change, update the canonical doc(s) in `docs/` first, then keep this pointer in sync.
