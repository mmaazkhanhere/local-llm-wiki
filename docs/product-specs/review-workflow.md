# Review Workflow

## Goal

Protect existing wiki pages when new or changed raw sources would modify already-generated knowledge.

## Observable Behavior

1. ingest must not rewrite an existing wiki page directly
2. the app ranks existing-page candidates using exact title matching and FTS5 search
3. the app runs an LLM coverage check using `Wiki/index.md` plus ranked candidates
4. if coverage is `covered` or `unsure`, ingest creates update proposals (review required) and does not create new wiki pages for that source
5. if coverage is `not_covered`, ingest may create brand-new wiki pages immediately
6. the app stores a proposal with reason, citation, current content, proposed content, and diff
7. the proposal appears in the `Proposed Updates` screen and in `Wiki/Reviews/`
8. the user can edit, approve, reject, or approve all proposals for one source
9. approval writes the target page atomically and updates related index or log entries when needed
10. rejection leaves the target wiki page unchanged
11. if the target page changed after proposal creation, the app marks the proposal as conflicted and refuses the write
12. every proposal lifecycle event and approved write is audited in SQLite and `.llm-wiki/audit.jsonl`

## Default Pending View

- show `pending` proposals
- keep `conflicted` proposals visible until the user resolves them
- hide `rejected` proposals from the default queue

## Safety Rules

- proposals must stay inside app-owned folders
- review files are generated artifacts, not raw input
- target wiki files stay unchanged until approval succeeds
- conflict detection uses the target page hash captured when the proposal was created
