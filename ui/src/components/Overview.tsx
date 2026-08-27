"use client";

import Link from "next/link";
import { useWorkspace } from "./WorkspaceProvider";
import { StatusPanel } from "./StatusPanel";

function displayDate(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(new Date(`${value}T00:00:00Z`));
}

export function Overview() {
  const { data, status } = useWorkspace();
  const coverage = [
    { label: "SEC filing records", value: String(data.filingCount), detail: "10-K · 10-Q · 8-K when available" },
    { label: "Normalized facts", value: String(data.factCount), detail: `Mapping ${data.quality.mappingVersion}` },
    { label: "Forensic tests", value: String(data.analytics.forensicTests), detail: `${data.analytics.computableTests} currently computable` },
    { label: "Ranked signals", value: String(data.signals.length), detail: "Deterministic screening only" },
  ];
  return (
    <>
      <header className="page-heading"><div><p className="eyebrow">Company overview</p><h1>{data.company.name}</h1><p>Trace SEC source records through normalized facts, deterministic tests, evidence, competing interpretations, and verification.</p></div><div className="run-status"><span className={`status-dot status-dot--${status === "ready" ? "success" : "warning"}`} />{data.source === "api" ? "Runtime API" : "Recorded fixture"}</div></header>
      <section className="command-strip" aria-label="Analysis shortcuts"><Link href="/financials">Inspect financial history <span>→</span></Link><Link href="/signals">Review ranked signals <span>→</span></Link><Link href="/investigation">Open live debate <span>→</span></Link><Link href="/geography">Explore source map <span>→</span></Link></section>
      <section className="coverage-panel" aria-labelledby="coverage-heading"><div className="section-heading"><div><p className="eyebrow">Deterministic foundation</p><h2 id="coverage-heading">Current coverage</h2></div><p>CIK {data.company.cik}</p></div><div className="coverage-grid">{coverage.map((item) => <dl key={item.label} className="coverage-item"><dt>{item.label}</dt><dd>{item.value}</dd><dd className="coverage-detail">{item.detail}</dd></dl>)}</div></section>
      <div className="overview-columns">
        <section className="records-panel" aria-labelledby="filings-heading"><div className="section-heading"><div><p className="eyebrow">SEC source records</p><h2 id="filings-heading">Recent filings</h2></div><p>All dates as filed</p></div><div className="table-wrap"><table><thead><tr><th scope="col">Form</th><th scope="col">Report period</th><th scope="col">Filed</th><th scope="col">Accession</th></tr></thead><tbody>{data.filings.slice(0, 8).map((filing) => <tr key={filing.accession}><td><span className="form-tag">{filing.form}</span></td><td>{displayDate(filing.reportPeriod)}</td><td>{displayDate(filing.filingDate)}</td><td className="mono">{filing.accession}</td></tr>)}</tbody></table></div>{!data.filings.length ? <StatusPanel state="empty" title="No prepared filings" detail="Choose a company above to fetch its SEC submissions and Company Facts records." /> : null}</section>
        <aside className="assessment-panel" aria-labelledby="assessment-heading"><p className="eyebrow">Accounting-quality status</p><h2 id="assessment-heading">{data.signals.length ? "Signals require review" : "No supported conclusion"}</h2><p>{data.signals.length ? "Deterministic screening found ranked items. Open Investigation to compare cited interpretations." : "The current evidence does not support an accounting-quality conclusion. No missing value is treated as zero."}</p><dl className="assessment-list"><div><dt>Normalized coverage</dt><dd>{data.factCount} facts</dd></div><div><dt>Quality findings</dt><dd>{data.quality.findings}</dd></div><div><dt>Computable tests</dt><dd>{data.analytics.computableTests}</dd></div><div><dt>Evidence packets</dt><dd>{data.evidence.length}</dd></div><div><dt>Map evidence</dt><dd>{data.geography.locations.length}</dd></div></dl></aside>
      </div>
      {data.error ? <StatusPanel state="stale" title="Recorded fallback is visible" detail={data.error} /> : data.quality.missingMetrics ? <StatusPanel state="partial" title="Partial financial coverage" detail={`${data.quality.missingMetrics} missing canonical metrics remain explicit. Tests without adequate inputs stay not computable.`} /> : null}
    </>
  );
}
