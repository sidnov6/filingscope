# FilingScope UI

This is the FilingScope institutional research workstation. It uses Next.js, React, TypeScript,
Salt Design System primitives, TanStack Table, TradingView Lightweight Charts, and project-owned
semantic tokens.

Routes:

- `/` — company overview with coverage, quality, and deterministic run status.
- `/financials` — normalized facts, period/unit context, sortable provenance, and trend chart.
- `/signals` — test coverage and explainable ranked-screening state.
- `/investigation` — aligned investigator/bull/skeptical and verification state.
- `/evidence` — exact excerpt, Evidence ID, accession, scope, and direct SEC link.
- `/audit` — stage status, versions, validation state, and export context.
- `/components-explorer` — loading, empty, partial, stale, and error states.

The shell supports comfortable and compact density, keyboard-visible focus, a skip link, responsive
desktop/tablet/mobile layouts, reduced motion, accessible table alternatives, and non-color status
labels. Set `FILINGSCOPE_API_URL` to use a running local API; otherwise the UI clearly uses its
recorded view model so static builds and offline review remain reproducible.
