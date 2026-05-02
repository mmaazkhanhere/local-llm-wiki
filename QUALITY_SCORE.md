# Quality Score

Use this rubric when judging whether a slice is ready to land.

## 100-Point Rubric

### Safety: 30

- raw notes never modified
- writes restricted to app-owned folders
- generated folders excluded from raw ingestion

### Reliability: 20

- repeated watcher events are harmless
- retries are bounded and intentional
- failures are visible and recoverable

### Grounding: 20

- generated claims cite evidence when practical
- ask answers stay within retrieved support
- unsupported claims are rejected

### Usability: 15

- setup is understandable
- states are visible
- errors are comprehensible

### Maintainability: 15

- provider abstraction is narrow
- schema and docs are current
- tests cover critical paths

## Release Gate

Do not treat an MVP slice as release-ready unless:

- Safety >= 28
- Reliability >= 16
- Grounding >= 16
- Total >= 85
