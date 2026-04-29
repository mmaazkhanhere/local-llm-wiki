# Frontend

## Scope

The frontend is a desktop UI for PySide6 or PyQt6.

The UI is not responsible for business logic. It should call core services and display state.

## Screen Contracts

### First-Run Wizard

Must support:

- select existing vault
- preview folders to be created
- enter provider key
- test provider connection
- start initial indexing

### Dashboard

Must show:

- selected vault path
- raw source count
- processed count
- queued or processing count
- last successful processing time
- provider status
- latest errors

### Sources

Must show:

- raw source path
- file type
- processing status
- last processed time
- last error if any

### LLM Wiki

Must show:

- generated page path
- page type
- source association
- generated timestamp

### Ask

Must show:

- user question input
- grounded answer
- cited summary pages
- cited raw source chunks
- unsupported-answer state

### Settings

Must allow:

- change vault path
- update provider key
- toggle automatic processing
- toggle Git integration

## UI State Model

Preferred status values:

- `discovered`
- `queued`
- `processing`
- `generated`
- `skipped`
- `failed`

## UI Error Handling

The UI must distinguish:

- provider auth failure
- rate limit or network failure
- file parsing failure
- file locked or unreadable
- unsupported type
- internal write failure

Errors must include:

- plain-language summary
- source file path when applicable
- retry recommendation when applicable
