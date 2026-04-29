# File Processing

## Scope

This spec covers how a raw file becomes generated Obsidian content.

## Processing Contract

1. detect supported file
2. exclude app-owned and metadata folders
3. debounce until stable write
4. hash file
5. skip if unchanged
6. extract text
7. store source document
8. chunk text
9. generate summary
10. write summary
11. update index and logs

## Supported File Types

Initial priority:

- `.md`
- `.txt`

Next priority:

- `.pdf`
- `.docx`
- `.html`
- `.htm`
- `.png`
- `.jpg`
- `.jpeg`
- `.webp`

## Filename Normalization

Summary filename generation must:

- preserve readability
- sanitize invalid Windows characters
- collapse whitespace
- trim trailing spaces and periods
- append page-type suffix
- append short hash on collision
