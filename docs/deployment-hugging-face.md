# Hugging Face Spaces deployment

FilingScope targets a Docker Space because one public port must serve both the FastAPI routes and
the exported Next.js workstation. The root `README.md` contains the required Space metadata and the
container listens on port 7860.

## Before the first push

1. Create a new Hugging Face Space with the Docker SDK.
2. Clone its repository and push this repository's contents, or add the Space Git URL as a remote.
3. In **Settings → Variables**, add a real `FILINGSCOPE_SEC_USER_AGENT` containing an operator name
   and monitored email. Add `FILINGSCOPE_GROQ_REASONING_MODEL` only when live investigations are
   enabled.
4. In **Settings → Secrets**, add `FILINGSCOPE_GROQ_API_KEY` only when live investigations are
   enabled. Never commit either provider or Hub tokens.
5. Keep CPU Basic for this deterministic demo. No GPU is required.

The Hugging Face access token used to push the Space is a deployment credential. It is not an app
runtime setting and must not be added to the Docker image or Space variables.

## Storage and operation

The image preloads the immutable Apple fixture into `/home/user/app/data`, so the UI and read-only
API work immediately. Default Space disk is ephemeral. For durable ingestions, reports, and caches,
attach a Storage Bucket at a chosen mount path and set `FILINGSCOPE_DATA_DIR` to that path.

Operational checks:

- `/health` confirms process and schema versions.
- `/ready` confirms the embedded DuckDB database and company count.
- `/runs/summary` reports complete, partial, deterministic-only, and provider-backed runs.
- `/version` exposes application, schema, and mapping versions.
- `/companies/search?q=AAPL` confirms directory search and reports whether live SEC lookup is
  available.
- `/investigations/stream` emits validated stage events as server-sent events.

The Docker build deliberately uses no secrets. Groq credentials are read only at runtime. SEC live
ingestion remains disabled until the operator identity variable is valid.
