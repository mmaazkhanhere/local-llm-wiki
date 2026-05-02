# Frontend

Frontend behavior is specified in `docs/product-specs/` and informed by `docs/design-docs/`.

Read in this order:

1. `docs/product-specs/new-user-onboarding.md`
2. `docs/product-specs/file-processing.md`
3. `docs/product-specs/ask-experience.md`
4. `docs/design-docs/index.md`

Frontend constraints:

- the UI displays state; core services own business logic
- raw-source immutability must be obvious in the interface
- generated outputs, citations, failures, and provider state must be visible

Treat this file as a router, not the canonical spec.
