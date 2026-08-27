"use client";

import { Button } from "@salt-ds/core";
import { useEffect, useMemo, useRef, useState } from "react";
import { StatusPanel } from "./StatusPanel";
import { useWorkspace } from "./WorkspaceProvider";

type Role = "planner" | "investigator" | "bull" | "skeptical" | "verifier" | "judge";
type EventStatus = "queued" | "running" | "complete" | "skipped" | "failed";
type InvestigationEvent = { sequence: number; run_id: string; role: Role | "system"; status: EventStatus; title: string; message: string; output?: Record<string, unknown>; emitted_at: string };
const roles: Array<{ id: Role; label: string; mandate: string }> = [
  { id: "planner", label: "Planner", mandate: "Bounds questions and evidence needs" },
  { id: "investigator", label: "Investigator", mandate: "Tests signals against filing evidence" },
  { id: "bull", label: "Bull analyst", mandate: "Builds the strongest benign explanation" },
  { id: "skeptical", label: "Skeptical analyst", mandate: "Challenges headline reporting quality" },
  { id: "verifier", label: "Verifier", mandate: "Checks every claim against exact citations" },
  { id: "judge", label: "Judge", mandate: "Uses only verified or uncertain claims" },
];

function yearsBefore(date: string, years: number) {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCFullYear(value.getUTCFullYear() - years);
  return value.toISOString().slice(0, 10);
}

function outputLines(event?: InvestigationEvent) {
  if (!event?.output) return [];
  const output = event.output;
  if (Array.isArray(output.questions)) return output.questions.map(String);
  if (Array.isArray(output.claims)) return output.claims.flatMap((claim) => typeof claim === "object" && claim && "text" in claim ? [String((claim as { text: unknown }).text)] : []);
  if (Array.isArray(output.verifications)) return output.verifications.flatMap((item) => typeof item === "object" && item && "explanation" in item ? [String((item as { explanation: unknown }).explanation)] : []);
  if (typeof output.summary === "string") return [output.summary];
  return [];
}

export function InvestigationArena() {
  const { data } = useWorkspace();
  const latestFact = useMemo(() => data.facts.map((fact) => fact.endDate).sort().at(-1) ?? new Date().toISOString().slice(0, 10), [data.facts]);
  const [startDate, setStartDate] = useState(() => yearsBefore(latestFact, 5));
  const [endDate, setEndDate] = useState(latestFact);
  const [events, setEvents] = useState<InvestigationEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("Ready to evaluate the deterministic gate.");
  const streamRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setEndDate(latestFact);
      setStartDate(yearsBefore(latestFact, 5));
      setEvents([]);
      setMessage("Ready to evaluate the deterministic gate.");
      streamRef.current?.close();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [data.company.cik, latestFact]);

  useEffect(() => () => streamRef.current?.close(), []);

  function start() {
    streamRef.current?.close();
    setEvents([]);
    setRunning(true);
    setMessage("Opening live investigation stream…");
    const parameters = new URLSearchParams({ cik: data.company.cik, start_date: startDate, end_date: endDate });
    const stream = new EventSource(`/investigations/stream?${parameters}`);
    streamRef.current = stream;
    stream.onmessage = (raw) => {
      const event = JSON.parse(raw.data) as InvestigationEvent;
      setEvents((current) => [...current.filter((item) => item.sequence !== event.sequence), event].sort((a, b) => a.sequence - b.sequence));
      setMessage(event.message);
      if (event.role === "system" && ["complete", "skipped", "failed"].includes(event.status)) {
        setRunning(false);
        stream.close();
      }
    };
    stream.onerror = () => {
      setRunning(false);
      setMessage("The stream closed before a valid terminal event. Existing deterministic data remains available.");
      stream.close();
    };
  }

  const latestByRole = Object.fromEntries(roles.map(({ id }) => [id, [...events].reverse().find((event) => event.role === id)])) as Record<Role, InvestigationEvent | undefined>;
  const terminal = [...events].reverse().find((event) => event.role === "system" && ["complete", "skipped", "failed"].includes(event.status));
  return (
    <>
      <div className="investigation-controls"><label>From<input type="date" value={startDate} max={endDate} onChange={(event) => setStartDate(event.target.value)} /></label><label>To<input type="date" value={endDate} min={startDate} onChange={(event) => setEndDate(event.target.value)} /></label><Button onClick={start} disabled={running}>{running ? "Investigation running…" : "Start live investigation"}</Button><p role="status" aria-live="polite">{message}</p></div>
      <section className="debate-ledger" aria-label="Live agent debate">
        <div className="debate-track" aria-hidden="true"><span className={events.length ? "active" : ""} /></div>
        {roles.map((role, index) => {
          const event = latestByRole[role.id];
          const lines = outputLines(event);
          const inferredStatus: EventStatus = terminal?.status === "skipped" && !event ? "skipped" : event?.status ?? "queued";
          return <article className={`agent-card agent-card--${inferredStatus}`} key={role.id} aria-label={`${role.label}: ${inferredStatus}`}><header><span>{String(index + 1).padStart(2, "0")}</span><div><p className="eyebrow">{role.label}</p><h2>{event?.title ?? (inferredStatus === "skipped" ? "Not called" : "Waiting")}</h2></div><strong>{inferredStatus}</strong></header><p>{event?.message ?? (inferredStatus === "skipped" ? "The deterministic gate or provider policy stopped this role." : role.mandate)}</p>{lines.length ? <ul>{lines.slice(0, 4).map((line, lineIndex) => <li key={`${lineIndex}-${line}`}>{line}</li>)}</ul> : null}</article>;
        })}
      </section>
      {terminal?.status === "skipped" ? <StatusPanel state="partial" title={terminal.title} detail={terminal.message} /> : terminal?.status === "failed" ? <StatusPanel state="error" title={terminal.title} detail={terminal.message} /> : null}
      <p className="debate-disclosure">The stream shows stage status and validated public outputs—not private chain-of-thought. Claims must retain fact, metric, or Evidence IDs before the judge can use them.</p>
    </>
  );
}
