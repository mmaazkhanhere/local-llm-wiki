# Security

Use this file as the concern-level router for security work.

Mandatory reads:

1. `docs/exec-plans/tech-debt-tracker.md`
2. `docs/design-docs/auto-write-safety.md`
3. `IMPLEMENTATION_PLAN.md`

Security invariants:

- keep vault data local by default
- minimize remote data exposure
- never write outside app-owned paths
- protect provider credentials
- reject unsafe path derivation

If a change weakens one of these invariants, add a debt entry instead of leaving the compromise undocumented.
