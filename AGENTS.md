# AGENTS (Router)

System of record: `docs/`. Top-level markdown files are pointers, not canonical.

## Read Order

1. This file
2. If touching a risky area: `docs/exec-plans/tech-debt-tracker.md`
3. Relevant `docs/` domain doc(s)
4. `IMPLEMENTATION_PLAN.md` when product/architecture context is needed

## Routing (Task -> Docs)

- Architecture/boundaries -> `ARCHITECTURE.md` -> `docs/design-docs/index.md` -> `docs/generated/db-schema.md`
- Product/UX -> `PRODUCT_SENSE.md`, `DESIGN.md`, `FRONTEND.md` -> `docs/product-specs/index.md`
- Execution sequencing -> `PLANS.md` -> `docs/exec-plans/active/`
- Reliability-sensitive work -> `RELIABILITY.md` -> `docs/exec-plans/tech-debt-tracker.md`
- Security-sensitive work -> `SECURITY.md` -> `docs/exec-plans/tech-debt-tracker.md`
- Quality gates/release bar -> `QUALITY_SCORE.md`
- External tools/ecosystem notes -> `docs/references/`

## Non-Negotiables

- Never modify raw user notes.
- Never treat generated wiki output as raw input.
- Never write outside app-owned folders in the target vault.
- Keep generated markdown editable and readable in Obsidian.
- Prefer deterministic, reversible, auditable behavior.
- Preserve source grounding over fluent but weak synthesis.
- Fail closed on unsafe paths, unsafe writes, and ambiguous state.

## Risky Areas (Read Debt Tracker First)

- path normalization / write-scope enforcement
- vault scanning / watcher exclusions
- database schema / migrations
- ingestion / chunk extraction
- generated markdown writes
- index / audit log updates
- retrieval ranking / grounding
- provider boundaries / retry logic
- secret storage / key handling

## Debt Tracker Rules

- Before changing a risky area: open `docs/exec-plans/tech-debt-tracker.md`, review `## Active Debt`, align mitigations/exit criteria.
- If introducing a compromise: add under `## Active Debt` with next `TD-###` and include `area`, `change trigger`, `compromise`, `risk`, `temporary mitigation`, `exit criteria`, `verification needed`.
- If fixing a compromise: move to `## Resolved Debt`, keep original problem statement, add `resolution summary`, `verification performed`, `date resolved`.
- Never delete debt entries silently.

## Documentation Rules

- When behavior/constraints/delivery order changes, update the canonical doc in `docs/` first.
- Keep docs short, explicit, and operational; prefer one canonical location per concept.
- If a top-level file and `docs/` disagree, fix `docs/` first, then repair the top-level pointer.
- Log every change in `change-log.md` using: `[DD/MM/YYYY HH:mm:ss] file_name:line_number <brief_explanation_of_changes_made>` (every change must be logged).

## Plans & Generated Docs

- Active work: `docs/exec-plans/active/` (move finished plans to `docs/exec-plans/completed/`).
- Generated reference docs: `docs/generated/` (regenerate when implementation invalidates them).

## When Unsure

- Prefer the safer write path and the more auditable workflow; follow doc-backed constraints over assumptions.
