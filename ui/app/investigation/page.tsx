"use client";

import { AppShell } from "@/src/components/AppShell";
import { InvestigationArena } from "@/src/components/InvestigationArena";
import { useWorkspace } from "@/src/components/WorkspaceProvider";

export default function InvestigationPage() {
  const { data } = useWorkspace();
  return <AppShell><header className="page-heading"><div><p className="eyebrow">Live investigation</p><h1>Competing explanations, streamed</h1><p>Watch planner, investigator, bull, skeptical, verifier, and judge stages advance only after deterministic screening and evidence controls permit them.</p></div><div className="run-status"><span className={`status-dot status-dot--${data.signals.length ? "success" : "warning"}`} />{data.signals.length} eligible signals</div></header><InvestigationArena /></AppShell>;
}
