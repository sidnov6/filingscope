---
title: FilingScope
emoji: 🔎
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# FilingScope

FilingScope is a deterministic-first SEC financial-intelligence and forensic-accounting research
system. This repository implements the complete local-first architecture path: SEC acquisition,
versioned normalization, deterministic metrics and forensic tests, robust anomaly context, signal
ranking, section-aware filing parsing, FTS5 evidence retrieval, bounded typed investigation,
verification, report/audit exports, FastAPI delivery, and an institutional Next.js workstation.

It identifies reporting risks and unusual patterns only after versioned deterministic tests exist.
It does not accuse companies of fraud, provide investment advice, or replace professional judgment.

## Backend setup

Python 3.12 is required.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
cp .env.example .env
# Replace the SEC User-Agent placeholders with an operator name and monitored email.
.venv/bin/uvicorn app.api.main:app --reload
```

`GET http://127.0.0.1:8000/health` reports the application and schema versions. No SEC request is
made merely by importing or starting the API.

Run the fully offline fixture ingestion:

```bash
.venv/bin/filingscope-offline-ingest \
  --fixtures tests/fixtures/sec \
  --data-dir data/offline-demo
```

The command writes immutable raw payloads/manifests under `data/offline-demo/raw/sec`, versioned
Parquet under `data/offline-demo/warehouse`, and DuckDB views in
`data/offline-demo/filingscope.duckdb`. Repeating it reuses valid cache entries and does not rewrite
unchanged Parquet files.

Run the same fixture through the full deterministic pipeline and persist normalized facts,
findings, metric results, 32 forensic-test results, anomalies, and signals:

```bash
.venv/bin/filingscope-offline-normalize \
  --fixtures tests/fixtures/sec \
  --data-dir data/offline-normalized-demo
```

Run the complete offline path through filing parsing, lexical indexing, deterministic investigation
fallback, and report/audit export:

```bash
.venv/bin/filingscope-offline-run \
  --fixtures tests/fixtures/sec \
  --data-dir data/offline-complete-demo
```

The exact mappings and period policy are in `docs/normalization-mappings.md`; formulas, forensic
tests, anomalies, quality, and peers are in `docs/deterministic-analysis.md`; evidence and agent
controls are in `docs/investigation-and-evidence.md`.

Core API routes:

- `GET /companies/search?q=...`
- `POST /companies/resolve`
- `POST /ingestion/{cik}`
- `GET /companies/{cik}/financials`
- `GET /companies/{cik}/signals`
- `GET /companies/{cik}/evidence`
- `GET /companies/{cik}/geography`
- `POST /investigations`
- `GET /investigations/stream?cik=...&start_date=...&end_date=...`
- `GET /investigations/{run_id}`
- `GET /evidence/{evidence_id}`
- `GET /reports/{run_id}?format=json|markdown`
- `GET /health`, `/ready`, `/version`, and `/cache/stats`
- `GET /runs/summary`

SEC access requires a real operator name and monitored email in `FILINGSCOPE_SEC_USER_AGENT`.
Agent investigation is optional and requires both `FILINGSCOPE_GROQ_API_KEY` and a configured model.
No provider call occurs when the values are absent or no signal qualifies.

## Frontend setup

```bash
cd ui
pnpm install
pnpm dev
```

The exported UI calls the same-origin FastAPI routes at runtime. The persistent company selector
searches the official SEC ticker directory when an identifiable SEC User-Agent is configured,
prepares a selected company on demand, and preserves its CIK in the URL. Routes cover Overview,
Financials, Signals, a live server-sent investigation ledger, Evidence, Geography, Audit, and the
component explorer. Financial tables use TanStack Table, the trend surface uses TradingView
Lightweight Charts, and the globe uses MapLibre GL. Geographic markers are limited to sourced
registered-address context and disclose centroid precision; they are not operating-exposure claims.

## Hugging Face deployment

The repository is a ready-to-push Docker Space. Its multi-stage image exports the Next.js UI,
installs the FastAPI backend as an unprivileged user, preloads the immutable offline fixture, and
serves both surfaces on port 7860. Build and smoke-test it locally with:

```bash
docker build -t filingscope-space .
docker run --rm -p 7860:7860 filingscope-space
curl http://127.0.0.1:7860/health
```

Set `FILINGSCOPE_GROQ_API_KEY` as a Space secret, and set
`FILINGSCOPE_GROQ_REASONING_MODEL` plus `FILINGSCOPE_SEC_USER_AGENT` as Space variables. Do not put
credentials in Git. The default Space filesystem is ephemeral; mount a Storage Bucket and point
`FILINGSCOPE_DATA_DIR` at it when investigation history must survive restarts. See
`docs/deployment-hugging-face.md` for the publish checklist.

## Verification

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest
cd ui
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

All automated tests run without live SEC access. Fixture origin and capture date are documented in
`tests/fixtures/sec/README.md`.

## Boundaries

The supplied SEC fixture is one intentionally small Apple excerpt, not the architecture’s desired
three-company, reviewed five-year corpus. It therefore produces six normalized facts, many explicit
missing-metric findings, 32 test results dominated by `not_computable`, and no ranked analytical
signal. This is correct behavior, not a demo conclusion.

Composite Beneish, Piotroski, and Altman entries remain explicit applicability failures until their
published component formulas and eligible-company policies receive a separate primary-source review.
Peer analysis requires an explicit cohort policy and at least the requested peer data. No live Groq
evaluation was run because credentials and a model were not supplied. These constraints do not
disable ingestion, normalization, analytics, retrieval mechanics, API/UI use, or deterministic-only
reports.

The next production-data step is to configure an identifiable SEC User-Agent and record reviewed
five-year fixtures for three companies. Then review composite-score applicability and peer policies
against that corpus before enabling those conclusions.
