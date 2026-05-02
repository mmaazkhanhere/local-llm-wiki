# Auto-Write Safety

## Decision

The repository is designed around generated writes landing automatically in app-owned areas.

## Why

- lower user friction
- faster path from source to usable wiki
- fewer review-queue mechanics in the MVP

## Required Safeguards

1. Never write outside app-owned folders.
2. Reject path traversal and unsafe path derivation.
3. Use atomic markdown writes.
4. Exclude generated folders from raw ingestion.
5. Record generated writes in durable app state and a human-readable log.
6. Surface failures instead of hiding partial success.

## Consequence

Because pre-write review is not the primary safety mechanism, write-scope enforcement and auditability are not optional.
