"use client";

import { AppShell } from "@/src/components/AppShell";
import { GeographyMap } from "@/src/components/GeographyMap";
import { useWorkspace } from "@/src/components/WorkspaceProvider";

export default function GeographyPage() {
  const { data } = useWorkspace();
  return <AppShell><header className="page-heading"><div><p className="eyebrow">Geographic evidence</p><h1>World context, without invented exposure</h1><p>Explore SEC-sourced registered-address context on a zoomable globe. Every marker exposes its source, precision, and analytical limitation.</p></div><div className="run-status">{data.company.ticker} · provenance on</div></header><GeographyMap /></AppShell>;
}
