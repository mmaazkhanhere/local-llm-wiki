# Ask Experience

## Goal

Answer questions from processed material using grounded evidence, not generic completion behavior.

## MVP Rules

- search generated wiki material first
- search raw chunks second
- cite evidence in the answer
- refuse unsupported claims
- preserve question state when provider calls fail

## Failure Rules

- if retrieval is weak, respond with uncertainty
- if evidence is missing, answer `Not supported by the current sources`
- if wiki wording exceeds raw support, prefer raw support
