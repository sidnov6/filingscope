"use client";

import { AppShell } from "@/src/components/AppShell";
import { DataQualityBadge } from "@/src/components/DomainComponents";
import { useWorkspace } from "@/src/components/WorkspaceProvider";

export default function AuditPage() {
  const { data } = useWorkspace();
  const stages = [
    ["Acquisition", data.filingCount ? "Complete" : "Empty", `${data.filingCount} filing records · immutable raw cache`],
    ["Normalization", data.factCount ? "Complete" : "Empty", `${data.factCount} facts · mapping ${data.quality.mappingVersion}`],
    ["Analytics", "Complete", `${data.analytics.forensicTests} versioned tests · ${data.analytics.computableTests} computable`],
    ["Evidence", data.evidence.length ? "Available" : "Pending", `${data.evidence.length} citation-ready packets`],
    ["Investigation", data.signals.length ? "Eligible" : "Deterministic only", `${data.signals.length} qualifying ranked signals`],
    ["Geography", data.geography.locations.length ? "Sourced" : "Unavailable", `${data.geography.locations.length} registered-address contexts`],
  ];
  return <AppShell><header className="page-heading"><div><p className="eyebrow">Run and audit</p><h1>Reproducibility chain</h1><p>Trace source, mapping, formula, test, evidence, prompt, cache, and validation state without exposing credentials.</p></div><div className="run-status">Schema 1.0.0</div></header><section className="data-panel"><div className="section-heading"><div><p className="eyebrow">Stage timeline</p><h2>{data.company.name}</h2></div><p>{data.company.ticker} · {data.company.cik}</p></div><ol className="audit-timeline">{stages.map(([stage, state, detail]) => <li key={stage}><span aria-hidden="true" /><div><strong>{stage}</strong><p>{detail}</p></div><DataQualityBadge state={["Complete", "Available", "Eligible", "Sourced"].includes(state) ? "verified" : "partial"}>{state}</DataQualityBadge></li>)}</ol></section></AppShell>;
}
