"use client";

import { useState } from "react";
import { AppShell } from "@/src/components/AppShell";
import { FinancialTable } from "@/src/components/FinancialTable";
import { StatusPanel } from "@/src/components/StatusPanel";
import { TrendChart } from "@/src/components/TrendChart";
import { useWorkspace } from "@/src/components/WorkspaceProvider";
import type { PeriodBasis } from "@/src/data/workspace";

export default function FinancialsPage() {
  const { data } = useWorkspace();
  const [basis, setBasis] = useState<PeriodBasis | "all">("all");
  const [metric, setMetric] = useState("all");
  const metrics = Array.from(new Set(data.facts.map((fact) => fact.metric))).sort();
  const facts = data.facts.filter((fact) => (basis === "all" || fact.basis === basis) && (metric === "all" || fact.metric === metric));
  const chartMetric = metric === "all" ? metrics.find((item) => data.facts.filter((fact) => fact.metric === item).length > 1) : metric;
  const points = data.facts.filter((fact) => fact.metric === chartMetric).map((fact) => ({ time: fact.endDate, value: fact.value })).sort((a, b) => a.time.localeCompare(b.time));
  return <AppShell>
    <header className="page-heading"><div><p className="eyebrow">Financial trends</p><h1>Normalized financial history</h1><p>Filter exact concept mappings while retaining period basis, confidence, accession, and fact-level provenance.</p></div><div className="run-status">{data.facts.length} prepared facts</div></header>
    <div className="filter-bar" aria-label="Financial filters"><label>Period basis<select value={basis} onChange={(event) => setBasis(event.target.value as PeriodBasis | "all")}><option value="all">All reported bases</option><option value="annual">Annual</option><option value="quarterly">Quarterly</option><option value="year_to_date">Year to date</option><option value="instant">Instant</option></select></label><label>Metric<select value={metric} onChange={(event) => setMetric(event.target.value)}><option value="all">All canonical metrics</option>{metrics.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><span>{facts.length} visible · mapping {data.quality.mappingVersion}</span></div>
    {data.error ? <StatusPanel state="stale" title="API unavailable; recorded fixture shown" detail={data.error} /> : null}
    {points.length > 1 && chartMetric ? <TrendChart points={points} label={chartMetric} /> : <StatusPanel state="empty" title="Trend needs comparable periods" detail="Choose a metric with at least two reported values. FilingScope never draws continuity across missing periods." />}
    <section className="data-panel"><div className="section-heading"><div><p className="eyebrow">Fact-level audit</p><h2>Reported values</h2></div><p>Sort with column headers</p></div><FinancialTable facts={facts} /></section>
  </AppShell>;
}
