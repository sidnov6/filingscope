"use client";

import { useState } from "react";
import { AppShell } from "@/src/components/AppShell";
import { StatusPanel } from "@/src/components/StatusPanel";
import { useWorkspace } from "@/src/components/WorkspaceProvider";

export default function EvidencePage() {
  const { data } = useWorkspace();
  const [selectedId, setSelectedId] = useState<string>();
  const selected = data.evidence.find((item) => item.id === selectedId) ?? data.evidence[0];
  return <AppShell>
    <header className="page-heading"><div><p className="eyebrow">Evidence viewer</p><h1>Exact filing passages</h1><p>Stable Evidence IDs resolve to section-aware excerpts, accessions, and direct SEC documents.</p></div><div className="run-status">{data.evidence.length} packet{data.evidence.length === 1 ? "" : "s"}</div></header>
    {selected ? <div className="evidence-layout"><section className="evidence-list" aria-label="Evidence packet list">{data.evidence.map((item) => <button key={item.id} aria-pressed={item.id === selected.id} onClick={() => setSelectedId(item.id)}><strong>{item.id}</strong><span>{item.section}</span><small>{item.accession}</small></button>)}</section><article className="evidence-reader"><p className="eyebrow">{selected.id}</p><h2>{selected.section}</h2><p className="filing-reference">SEC filing · {selected.accession}</p><blockquote>{selected.excerpt}</blockquote><p className="evidence-scope">Exact recorded excerpt only. Absence elsewhere was not tested and is not inferred.</p><a className="source-link" href={selected.sourceUrl} target="_blank" rel="noreferrer">Open source filing at SEC.gov</a></article></div> : <StatusPanel state="empty" title="No citation-ready packet" detail="Evidence packets appear only after a ranked signal produces a bounded retrieval request." />}
  </AppShell>;
}
