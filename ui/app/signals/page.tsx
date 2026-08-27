"use client";

import { useState } from "react";
import { AppShell } from "@/src/components/AppShell";
import { SeverityBadge } from "@/src/components/DomainComponents";
import { StatusPanel } from "@/src/components/StatusPanel";
import { useWorkspace } from "@/src/components/WorkspaceProvider";

export default function SignalsPage() {
  const { data } = useWorkspace();
  const [severity, setSeverity] = useState("all");
  const signals = data.signals.filter((signal) => severity === "all" || signal.severity === severity);
  return <AppShell>
    <header className="page-heading"><div><p className="eyebrow">Signal workspace</p><h1>Deterministic screening signals</h1><p>Ranks are screening priorities—not findings of misconduct—and expose their formula context and confidence.</p></div><div className="run-status">{data.analytics.forensicTests} tests evaluated</div></header>
    <div className="summary-strip"><div><span>Metric results</span><strong>{data.analytics.metricResults}</strong></div><div><span>Forensic tests</span><strong>{data.analytics.forensicTests}</strong></div><div><span>Computable tests</span><strong>{data.analytics.computableTests}</strong></div><div><span>Ranked signals</span><strong>{data.signals.length}</strong></div></div>
    <div className="filter-bar"><label>Severity<select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option><option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option><option value="critical">Critical</option></select></label><span>{signals.length} visible signals</span></div>
    {signals.length ? <section className="data-panel"><div className="table-wrap"><table><thead><tr><th>Test</th><th>Category</th><th>Severity</th><th>Score</th><th>Explanation</th></tr></thead><tbody>{signals.map((signal) => <tr key={signal.id}><td>{signal.test}</td><td>{signal.category}</td><td><SeverityBadge severity={signal.severity} /></td><td>{signal.score.toFixed(3)}</td><td className="wrap-cell">{signal.reason}</td></tr>)}</tbody></table></div></section> : <StatusPanel state="empty" title="No ranked signal met policy" detail="The selected history does not support a robust ranked anomaly. This is not evidence that accounting risk is absent." />}
  </AppShell>;
}
