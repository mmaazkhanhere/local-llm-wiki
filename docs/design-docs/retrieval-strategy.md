# Retrieval Strategy

## MVP Retrieval

First pass uses simple text retrieval only.

Order:

1. search generated summaries
2. search raw source chunks
3. combine evidence
4. answer with citations

## Why No Embeddings Yet

- not required for first-pass usefulness
- reduces implementation complexity
- avoids extra storage and provider coupling
- keeps failure surface smaller

## Answering Rules

- if summary and raw chunk disagree, trust raw chunk
- if raw support is partial, qualify the answer
- if raw support is absent, say so explicitly
