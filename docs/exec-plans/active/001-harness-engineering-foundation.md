# 001 Harness Engineering Foundation

## Objective

Establish a repository-level knowledge base that agents can use as a routing and decision system.

## Scope

- restore `AGENTS.md` as the first-read router
- make `docs/` the system of record
- add design, product, execution, generated, and reference doc buckets
- define debt-tracker workflow for risky changes
- keep top-level docs as thin entry points into `docs/`

## Dependencies

- `IMPLEMENTATION_PLAN.md`
- current top-level concern docs

## Acceptance Criteria

- `AGENTS.md` points to the correct docs
- risky-area work is explicitly gated on checking the debt tracker
- `docs/exec-plans/tech-debt-tracker.md` supports active and resolved debt
- product and design docs are discoverable from indexes
- database schema reference exists under `docs/generated/`

## Risks

- top-level docs may drift from canonical docs if treated as full specs
- debt tracking can become performative unless entries remain specific and honest

## Exit

Move this plan to `completed/` when the docs structure is stable and being used during implementation work.
