# ADR 0003: Deterministic analytics, lexical evidence, and gated investigation

- Status: Accepted
- Date: 2026-08-27

## Decision

- Keep formulas and tests in versioned registries independent of provider code.
- Return `not_computable` for missing inputs, zero denominators, unknown applicability, and
  insufficient peer or anomaly samples.
- Use the NIST modified-z potential-outlier policy only as moderate screening priority.
- Require caller-supplied peer cohort thresholds rather than embedding economic assumptions.
- Use section-aware HTML parsing and SQLite FTS5 before considering embeddings.
- Treat filing text as untrusted evidence and enforce exact ID references at every agent boundary.
- Cache only schema-valid provider outputs and preserve deterministic-only completion.
- Export JSON, Markdown, and an audit manifest for each run.

## Consequences

The complete pipeline can operate offline and degrades honestly. Composite screens, broad retrieval
claims, peer conclusions, and agent conclusions cannot appear until their required inputs and
explicit applicability policies exist.
