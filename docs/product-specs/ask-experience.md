# Ask Experience

## Goal

Let the user ask questions over processed material and receive grounded answers with citations.

## MVP Rules

- simple text retrieval only
- embeddings are not required
- summaries searched first
- raw chunks searched second
- answers must cite evidence
- unsupported claims must be refused

## Failure Rules

- if no useful evidence is retrieved, answer `Not supported by the current sources`
- if summary wording exceeds raw support, prefer raw support
- if provider call fails, preserve question state and show retryable error
