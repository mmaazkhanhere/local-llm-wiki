# Retrieval Strategy

## MVP Retrieval Order

1. search generated wiki material first
2. search raw source chunks second
3. combine evidence carefully
4. answer only within retrieved support

## Principles

- prefer the compiled wiki for speed and reuse
- use raw material for verification and citation
- if wiki text and raw evidence disagree, trust raw evidence
- if support is partial, qualify the answer
- if support is absent, refuse the claim

## Deferred Complexity

Embeddings, vector databases, and heavy ranking systems are deferred until lexical retrieval is demonstrably inadequate.
