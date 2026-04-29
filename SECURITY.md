# Security

## Security Goals

- keep vault data local
- minimize accidental data disclosure
- avoid writing outside app-owned folders
- protect provider credentials

## Data Handling

Local storage:

- vault content remains in the user-selected vault
- app state lives in `.llm-wiki/`
- generated content lives in `LLM Wiki/`

Remote exposure:

- only extracted content sent to configured provider should leave the machine
- UI must clearly explain that provider-backed processing may transmit note content

## Credential Handling

Preferred:

- OS keychain via Python `keyring`

Fallback:

- encrypted local config only if keychain is unavailable

Never:

- hardcode keys
- log keys
- echo keys in UI diagnostics

## Path-Safety Rules

- normalize and resolve all output paths before write
- reject any output path that escapes the vault root
- reject any generated path outside `LLM Wiki/` or `.llm-wiki/`
- never derive write targets from unsanitized raw path strings alone

## Git Safety

If Git integration is enabled:

- commit only generated files and app-owned audit files by default
- never auto-stage untracked raw notes
- never assume the whole vault should be committed
