"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchWorkspace, recordedFixture, type CompanySearchResult, type WorkspaceData } from "../data/workspace";

type WorkspaceStatus = "loading" | "ready" | "preparing" | "error";
type WorkspaceContextValue = { data: WorkspaceData; status: WorkspaceStatus; statusMessage: string; setStatusMessage: (message: string) => void; selectCompany: (company: CompanySearchResult) => Promise<void>; refresh: () => Promise<void> };
const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [data, setData] = useState(recordedFixture);
  const [status, setStatus] = useState<WorkspaceStatus>("loading");
  const [statusMessage, setStatusMessage] = useState("Loading prepared SEC workspace…");

  const load = useCallback(async (cik: string) => {
    try {
      const next = await fetchWorkspace(cik);
      setData(next);
      setStatus("ready");
      setStatusMessage(`Loaded ${next.company.name} from the FilingScope API.`);
    } catch (error) {
      setStatus("error");
      setStatusMessage(error instanceof Error ? error.message : "The company workspace could not be loaded.");
      if (cik === recordedFixture.company.cik) setData({ ...recordedFixture, error: "Live API unavailable; recorded fixture retained." });
    }
  }, []);

  useEffect(() => {
    const cik = new URL(window.location.href).searchParams.get("company") ?? recordedFixture.company.cik;
    const timeout = window.setTimeout(() => void load(cik), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  const selectCompany = useCallback(async (company: CompanySearchResult) => {
    setStatus("preparing");
    setStatusMessage(company.locallyAvailable ? `Opening ${company.name}…` : `Fetching and analyzing SEC filings for ${company.name}…`);
    try {
      if (!company.locallyAvailable) {
        const response = await fetch(`/ingestion/${company.cik}`, { method: "POST" });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({})) as { detail?: string };
          throw new Error(payload.detail ?? "SEC ingestion could not be completed.");
        }
      }
      const next = await fetchWorkspace(company.cik);
      setData(next);
      setStatus("ready");
      setStatusMessage(`Prepared ${next.company.name}: ${next.factCount} normalized facts and ${next.analytics.forensicTests} tests.`);
      const url = new URL(window.location.href);
      url.searchParams.set("company", company.cik);
      window.history.replaceState({}, "", url);
    } catch (error) {
      setStatus("error");
      setStatusMessage(error instanceof Error ? error.message : "Company preparation failed safely.");
    }
  }, []);

  const refresh = useCallback(async () => {
    setStatus("loading");
    setStatusMessage(`Refreshing ${data.company.name}…`);
    await load(data.company.cik);
  }, [data.company.cik, data.company.name, load]);

  const value = useMemo(() => ({ data, status, statusMessage, setStatusMessage, selectCompany, refresh }), [data, refresh, selectCompany, status, statusMessage]);
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}
