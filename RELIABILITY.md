# Reliability

## Goal

The app must process files automatically without corrupting state, thrashing the watcher, or silently dropping failures.

## Reliability Principles

- retries only for transient errors
- no infinite retry loops
- every failed operation leaves a visible status
- writes are atomic
- duplicate watcher events must be harmless

## Status Model

Recommended file processing statuses:

- `discovered`
- `queued`
- `processing`
- `generated`
- `skipped_unchanged`
- `failed_transient`
- `failed_permanent`

## Retry Policy

### Watcher and Stable Write Detection

- debounce filesystem events for 1000 ms
- if file size or modified time is still changing, wait again
- maximum stable-write wait window: 10 seconds
- if still unstable after 10 seconds, mark `failed_transient`

### Hashing and Local Reads

- retry locked-file reads up to 2 times
- backoff schedule: 500 ms, then 1000 ms
- do not retry missing-file errors if the file is gone by the time processing starts

### Extraction

Transient retry cases:

- temporary file lock
- temporary parser subprocess failure

Permanent failure cases:

- corrupt PDF
- unsupported encoding after fallback attempts
- malformed DOCX that parser cannot open

Policy:

- maximum 2 retries for transient extraction failures
- no retries for clearly permanent parse failures

### Provider Calls

Retry only for:

- network timeout
- connection reset
- HTTP 429
- HTTP 5xx

Do not retry for:

- invalid API key
- unauthorized request
- unsupported model
- malformed prompt request

Provider retry policy:

- maximum 3 attempts total
- backoff schedule: 1s, 2s, 4s
- add jitter if implementation is simple

### Database Writes

- set SQLite busy timeout to 5000 ms
- retry transient `database is locked` errors up to 2 times
- use transactions around grouped status updates plus generated page writes

### Markdown Writes

- write to temp file in target directory
- fsync if practical
- rename atomically to final destination
- retry file-lock errors up to 2 times

## Failure Handling Rules

### If Extraction Fails

- do not call the LLM
- set file status to `failed_permanent` or `failed_transient`
- store concise error summary in `files.error_message`
- surface the error in the UI
- add audit entry only for write events, not parse failures

### If Summary Generation Fails

- do not write partial Markdown
- keep extracted text and chunks
- set file status appropriately
- allow later reprocessing without re-extracting when hash is unchanged and extracted content is already present

### If Index or Log Update Fails After Markdown Write

- treat this as a write-path failure
- retry the index/log update
- if still failing, keep the generated file but mark the record inconsistent
- surface a repair-needed status in UI

### If Audit Log Write Fails

- database transaction should still commit the core generated page state
- retry human-readable audit log write up to 2 times
- if it still fails, record a repair-needed event in SQLite

## Idempotency Rules

- reprocessing the same unchanged file must not create duplicate generated pages
- repeated watcher events for the same unchanged hash must converge to no-op
- index page rebuilds must be deterministic

## Q&A Reliability Rules

- first pass uses simple text retrieval only
- embeddings are not required for MVP
- if retrieval confidence is weak, answer with uncertainty
- if evidence is missing, answer `Not supported by the current sources`
