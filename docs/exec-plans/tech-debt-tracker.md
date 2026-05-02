# Tech Debt Tracker

Check this file before changing risky areas.

## Active Debt

### TD-001 Retrieval Simplicity Over Recall

Area: retrieval
Change trigger: MVP prioritizes simple text retrieval.
Compromise: lexical retrieval may miss relevant context in larger vaults.
Risk: grounded answers can underperform before architecture is ready for heavier retrieval.
Temporary mitigation: search generated wiki first, then raw chunks, and refuse weakly supported answers.
Exit criteria: measured retrieval misses justify embeddings or improved ranking.
Verification needed: benchmark representative question sets against current retrieval.

### TD-002 File-Type Coverage Is Intentionally Narrow

Area: ingestion
Change trigger: MVP focuses on the stable core path first.
Compromise: rich formats and images remain behind the markdown and text path.
Risk: users can import unsupported files before extraction reliability is ready.
Temporary mitigation: expose clear unsupported or pending-image states.
Exit criteria: markdown/text flow is stable and additional parsers are covered by tests.
Verification needed: file-type expansion tests and failure-mode review.

### TD-003 Repair Tooling Is Incomplete

Area: reliability
Change trigger: initial delivery focuses on core ingest and write paths.
Compromise: partial-failure repair commands may lag behind primary write behavior.
Risk: index, audit, or status drift can require manual cleanup during early iterations.
Temporary mitigation: keep writes atomic where possible and surface repair-needed states.
Exit criteria: add deterministic repair flows for index, audit, and consistency checks.
Verification needed: simulate partial failures and confirm successful repair.

## Resolved Debt

No resolved entries yet.

## Entry Rules

- Add new debt when a change knowingly trades correctness, safety, maintainability, or scope for delivery speed.
- Be specific about the compromise. Vague debt entries are not useful.
- Do not remove debt silently. Move resolved debt to the resolved section with verification.
- Keep wording honest so markdown history reflects the real engineering tradeoff.
