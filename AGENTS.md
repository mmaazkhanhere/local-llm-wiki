# AGENTS

## Purpose

This file routes agents to the repository's system of record.

Canonical project knowledge lives in `docs/`.
Top-level markdown files are short entry points, not the source of truth.

## Default Read Order

1. Read this file first.
2. Read `docs/exec-plans/tech-debt-tracker.md` before touching risky areas.
3. Read the relevant domain doc from `docs/`.
4. Read `IMPLEMENTATION_PLAN.md` when a decision needs product or architecture context.

## Routing

Use these docs based on the task:

- Architecture and boundaries: `ARCHITECTURE.md`, then `docs/design-docs/index.md`, then `docs/generated/db-schema.md`
- Product behavior and UX: `PRODUCT_SENSE.md`, `DESIGN.md`, `FRONTEND.md`, then `docs/product-specs/index.md`
- Execution sequencing: `PLANS.md`, then `docs/exec-plans/active/`
- Reliability-sensitive work: `RELIABILITY.md`, then `docs/exec-plans/tech-debt-tracker.md`
- Security-sensitive work: `SECURITY.md`, then `docs/exec-plans/tech-debt-tracker.md`
- Quality gates and release bar: `QUALITY_SCORE.md`
- External tool or ecosystem notes: `docs/references/`

## Non-Negotiable Constraints

- Never modify raw user notes.
- Never treat generated wiki output as raw input.
- Never write outside app-owned folders in the target vault.
- Keep generated markdown editable and readable in Obsidian.
- Prefer deterministic, reversible, and auditable behavior.
- Preserve source grounding over fluent but weak synthesis.
- Fail closed on unsafe paths, unsafe writes, and ambiguous state.

## Risky Areas

Always read the debt tracker before editing:

- path normalization and write-scope enforcement
- vault scanning and watcher exclusions
- database schema and migrations
- ingestion and chunk extraction
- generated markdown writes
- index and audit log updates
- retrieval ranking and answer grounding
- provider boundaries and retry logic
- secret storage and key handling

## Debt Tracker Workflow

Before changing a risky area:

1. Open `docs/exec-plans/tech-debt-tracker.md`.
2. Check active debt for known compromises, sharp edges, and temporary decisions.
3. Align your change with existing mitigation and exit criteria.

If you introduce a compromise:

1. Add a new entry under `## Active Debt`.
2. Use the next available `TD-###` identifier.
3. Record:
   - area
   - change trigger
   - compromise
   - user or engineering risk
   - temporary mitigation
   - exit criteria
   - verification needed

If you fix a compromise:

1. Move the entry to `## Resolved Debt`.
2. Keep the original problem statement.
3. Add:
   - resolution summary
   - verification performed
   - date resolved

Do not silently delete debt entries.
Human review depends on honest markdown history.

## Documentation Expectations

- Update the relevant doc when behavior, constraints, or delivery order changes.
- Keep docs short, explicit, and operational.
- Prefer one canonical location per concept.
- If a top-level file and a `docs/` file disagree, fix the `docs/` file first and then repair the router file.

## Implementation Bias

- Start with the smallest safe slice.
- Land safety infrastructure before richer automation.
- Keep provider-specific logic behind narrow interfaces.
- Prefer simple retrieval before heavier retrieval systems.
- Add schema or process complexity only when the current shape breaks down.

## Execution Plans

- Put active work in `docs/exec-plans/active/`.
- Move finished plans to `docs/exec-plans/completed/`.
- Keep plans concrete: scope, dependencies, risks, acceptance criteria.

## Generated Knowledge

Generated reference docs belong in `docs/generated/`.
Regenerate them when implementation changes invalidate the document.

## When Unsure

- Choose the safer write path.
- Choose the more auditable workflow.
- Choose the doc-backed interpretation over unstated assumptions.
