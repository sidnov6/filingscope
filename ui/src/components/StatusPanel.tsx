"use client";

import { Button } from "@salt-ds/core";

export type StatusState = "empty" | "loading" | "partial" | "stale" | "error";

const stateLabels: Record<StatusState, string> = {
  empty: "Empty",
  loading: "Loading",
  partial: "Partial data",
  stale: "Stale data",
  error: "Error",
};

export function StatusPanel({
  state,
  title,
  detail,
  actionLabel,
}: Readonly<{
  state: StatusState;
  title: string;
  detail?: string;
  actionLabel?: string;
}>) {
  if (state === "loading") {
    return (
      <section className="status-panel" aria-label={title} aria-busy="true" aria-live="polite">
        <span className="state-label">{stateLabels[state]}</span>
        <div className="skeleton skeleton--heading" />
        <div className="skeleton" />
        <div className="skeleton skeleton--short" />
        <span className="sr-only">{title}</span>
      </section>
    );
  }
  return (
    <section
      className={`status-panel status-panel--${state}`}
      aria-label={`${stateLabels[state]}: ${title}`}
      role={state === "error" ? "alert" : "status"}
    >
      <span className="state-label">{stateLabels[state]}</span>
      <h2>{title}</h2>
      {detail ? <p>{detail}</p> : null}
      {actionLabel ? <Button>{actionLabel}</Button> : null}
    </section>
  );
}
