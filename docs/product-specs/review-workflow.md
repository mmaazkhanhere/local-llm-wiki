# Review Workflow

## Goal

Protect existing wiki pages when new or changed raw sources would modify already-generated knowledge.

## Observable Behavior

1. ingest may still create brand-new wiki pages immediately
2. ingest must not rewrite an existing wiki page directly
3. the app finds related existing pages from the new source
4. the app stores a proposal with reason, citation, current content, proposed content, and diff
5. the proposal appears in the `Proposed Updates` screen and in `Wiki/Reviews/`
6. the user can edit, approve, reject, or approve all proposals for one source
7. approval writes the target page atomically and updates related index or log entries when needed
8. rejection leaves the target wiki page unchanged
9. if the target page changed after proposal creation, the app marks the proposal as conflicted and refuses the write
10. every proposal lifecycle event and approved write is audited in SQLite and `.llm-wiki/audit.jsonl`

## Default Pending View

- show `pending` proposals
- keep `conflicted` proposals visible until the user resolves them
- hide `rejected` proposals from the default queue

## Safety Rules

- proposals must stay inside app-owned folders
- review files are generated artifacts, not raw input
- target wiki files stay unchanged until approval succeeds
- conflict detection uses the target page hash captured when the proposal was created
