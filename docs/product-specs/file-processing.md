# File Processing

## Goal

Turn a supported raw file into generated wiki artifacts without mutating the source file.

## Processing Contract

1. detect a candidate source file
2. exclude app-owned and metadata folders
3. debounce until the file is stable
4. hash the file
5. skip unchanged files
6. extract normalized text
7. store source-document metadata
8. create retrieval chunks
9. generate brand-new wiki output immediately
10. generate review proposals for existing pages when needed
11. write only approved existing-page updates atomically
12. update index, logs, audit, and status

## Initial File Priority

- `.md`
- `.txt`

## Next File Priority

- `.pdf`
- `.docx`
- `.html`
- `.htm`
- image formats as pending or future work

## Filename Rules

Generated filenames must:

- remain readable
- be safe on Windows
- sanitize forbidden characters
- collapse duplicate whitespace
- trim trailing spaces and periods
- use deterministic suffixes
- append a short hash only when needed to break collisions
