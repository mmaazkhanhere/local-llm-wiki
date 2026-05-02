# Reliability

Use this file as the concern-level router for reliability work.

Mandatory reads:

1. `docs/exec-plans/tech-debt-tracker.md`
2. `docs/product-specs/file-processing.md`
3. `docs/design-docs/auto-write-safety.md`

Reliability rules:

- retries are only for transient failures
- writes must be atomic where practical
- duplicate watcher events must converge safely
- failures must leave visible state
- partial write-path failures must be repairable

If a reliability tradeoff is introduced, record it in the debt tracker immediately.
