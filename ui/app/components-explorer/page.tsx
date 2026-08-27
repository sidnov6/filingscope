import { AppShell } from "@/src/components/AppShell";
import { StatusPanel } from "@/src/components/StatusPanel";

export default function ComponentsExplorer() {
  return (
    <AppShell>
      <header className="page-heading">
        <p className="eyebrow">Component explorer</p>
        <h1>Operational states</h1>
        <p>Reference states for missing, delayed, incomplete, stale, and failed data.</p>
      </header>
      <section className="explorer-grid" aria-label="Operational state examples">
        <StatusPanel state="loading" title="Loading submissions" />
        <StatusPanel
          state="empty"
          title="No investigation exists"
          detail="Ingest and validate source data before creating an investigation."
          actionLabel="Return to overview"
        />
        <StatusPanel
          state="partial"
          title="Partial source coverage"
          detail="Two quarterly periods are present; annual coverage has not been ingested."
        />
        <StatusPanel
          state="stale"
          title="Cached source data"
          detail="Last fixture capture: 27 Aug 2026. Refresh requires an identified SEC client."
        />
        <StatusPanel
          state="error"
          title="Company Facts unavailable"
          detail="The valid submissions cache was preserved. Diagnostic: FS-SEC-001."
          actionLabel="Retry safely"
        />
      </section>
    </AppShell>
  );
}

