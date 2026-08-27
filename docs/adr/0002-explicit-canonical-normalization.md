# ADR 0002: Explicit canonical normalization and period selection

- Status: Accepted
- Date: 2026-08-27

## Context

Company Facts can contain multiple concepts, units, reporting contexts, and filing versions for what
an analyst may regard as one financial metric. Silent aliasing, period coercion, or amendment
preference would make downstream calculations difficult to reproduce and audit.

## Decision

- Version exact taxonomy-to-canonical mappings independently from storage schemas.
- Begin with only `us-gaap:Assets`, `us-gaap:Revenues`, and `us-gaap:NetIncomeLoss` after checking
  their FASB taxonomy definitions and instant/duration types.
- Reject incompatible units and period types. Emit findings for unmapped, missing, invalid,
  duplicate, unsupported-form, and amendment-selected cases.
- Classify periods from SEC frames first, then documented duration windows. Preserve ambiguous
  durations as `other_duration` and keep year-to-date separate from standalone quarters.
- Prefer original filings unless a caller explicitly chooses amendments or target accessions.
- Persist selected facts and findings in mapping-versioned Parquet partitions exposed through
  DuckDB, retaining source-manifest provenance and stable identifiers.
- Review a committed Apple golden projection in offline tests and require idempotent persistence.

## Consequences

The slice is narrow but auditable: unsupported concepts remain visible instead of being guessed,
and cumulative periods cannot enter the default quarterly view. Adding aliases, currencies, derived
quarters, or metrics requires a mapping-version change, source review, and new golden cases.
