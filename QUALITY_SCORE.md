# Quality Score

## Quality Rubric

Every milestone should be evaluated on a 100-point rubric.

### Safety: 30

- raw notes never modified
- writes restricted to app-owned folders
- excluded folders never re-ingested

### Reliability: 20

- watcher handles repeated events safely
- retries are bounded and correct
- failures are visible and recoverable

### Grounding: 20

- summaries cite source evidence
- Q&A answers are supported by retrieved material
- unsupported claims are rejected

### Usability: 15

- first-run setup is understandable
- file states are visible
- errors are comprehensible

### Maintainability: 15

- provider abstraction is clean
- schema is documented
- modules are coherent
- tests cover critical paths

## Release Gate

No MVP release candidate should ship unless:

- Safety >= 28
- Reliability >= 16
- Grounding >= 16
- Total >= 85
