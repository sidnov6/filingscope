# ADR 0001: Local deterministic acquisition foundation

- Status: Accepted
- Date: 2026-08-27

## Context

The architecture requires raw SEC provenance, offline repeatability, CIK-first identity, and local
analytical persistence before normalization, forensic calculations, evidence retrieval, or model
orchestration.

## Decision

- Use `src/filingscope` as the single Python package root, with plain functional subpackages.
- Keep the FastAPI delivery boundary in `app/api`; acquisition and storage code do not import it.
- Preserve SEC response bytes at content-addressed paths. An immutable manifest is keyed by canonical
  URL plus content hash; a small replaceable URL index points to the last valid cache entry.
- Use ETag and Last-Modified conditional requests after configured freshness expires. A 304 reuses
  the prior immutable payload and manifest.
- Persist companies, filing metadata, and raw XBRL facts as schema-versioned Parquet datasets, then
  expose DuckDB views over them. Repeated equivalent writes leave Parquet files untouched.
- Treat the committed Apple inputs as schema-preserving recorded excerpts. They prove ingestion
  contracts and provenance mechanics but are not normalization goldens or analytical facts.
- Require the operator's SEC User-Agent identity only when SEC access is constructed, so health and
  fully offline workflows do not require placeholder credentials.

## Consequences

The first slice can be exercised without live network access and malformed payloads cannot emit
derived records. A future refresh of an unchanged URL and content deliberately returns the original
manifest retrieval timestamp; attempt-level operational telemetry is a separate concern. Canonical
normalization, period selection, formula versions, forensic thresholds, filing parsing, retrieval,
and agent workflows remain unimplemented.

