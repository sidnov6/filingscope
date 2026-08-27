# Filing evidence, investigation, and report controls

Parser version: `1.0.0`  
Prompt version: `1.0.0`

## Filing and evidence pipeline

Primary filing URLs are constructed from CIK, accession, and the SEC-reported primary document.
The existing SEC client supplies allowlisting, size limits, caching, hashing, pacing, and manifests.
The parser ignores active/navigation content, detects Item boundaries, preserves table text, and
chunks within sections. Chunk IDs hash the source content, parser version, accession, section,
sequence, and text.

SQLite FTS5 provides lexical ranking with CIK, form, accession, and section filters. Evidence packets
retain stable IDs, exact offsets, minimal excerpts, direct SEC URLs, source hashes, parser versions,
selection reasons, and token counts. Filing text is always marked untrusted input.

The labeled recorded-excerpt evaluation currently has Recall@3 = 1.0 and MRR = 1.0 for its three
questions. This validates mechanics only; it is not a broad retrieval-quality claim.

## Investigation workflow

The bounded workflow is planner → investigator → bull → skeptical → verifier → judge. Each provider
response validates against a Pydantic schema. Role budgets are configurable, validated cache keys
include signal/evidence/model/prompt state, and only valid outputs are cached.

- Every role must cover every ranked signal.
- Material claims require evidence, fact, or metric IDs.
- Unknown references stop the agent branch safely.
- The verifier must return exactly one result for every claim and may inspect only evidence cited by
  that claim.
- Only supported or partially supported claims are sent to the judge.
- The judge receives no full database and may introduce no new facts.
- Accusatory fraud language is rejected by the final assessment schema.
- When the provider is absent, invalid, or exhausted, deterministic results and report exports still
  complete; agent sections remain pending.

The Groq adapter is deliberately small, uses JSON-only structured output, restricts its host, and
keeps API keys environment-backed. Model names and quotas are configuration, not architecture.

## Exports and audit

Every completed run can emit validated JSON, a human-readable Markdown report, and an audit manifest
linking normalized fact IDs → metric results → test results → signals → evidence → verified claims.
Reports distinguish deterministic results, evidence, interpretations, and limitations and include a
prominent non-accusation/non-investment-advice disclosure.
