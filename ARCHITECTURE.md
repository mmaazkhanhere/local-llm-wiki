# Architecture

The system-of-record architecture docs live in `docs/`.

Read in this order:

1. `docs/design-docs/index.md`
2. `docs/generated/db-schema.md`
3. `IMPLEMENTATION_PLAN.md`

Current architecture direction:

- local-first desktop application
- persistent wiki compiled from raw sources
- strict separation between raw data, generated wiki output, and hidden app state
- simple, auditable retrieval before higher-complexity retrieval systems

If architecture changes, update the canonical doc in `docs/` first.
