import type { PeriodBasis } from "../data/workspace";

export function MetricValue({ value, unit = "USD" }: Readonly<{ value: number; unit?: string }>) {
  const formatted = unit === "USD"
    ? new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value)
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(value);
  return <span className="metric-value"><span>{formatted}</span><small>{unit}</small></span>;
}

export function DataQualityBadge({ state, children }: Readonly<{ state: "verified" | "partial" | "missing"; children: React.ReactNode }>) {
  return <span className={`quality-badge quality-badge--${state}`}>{children}</span>;
}

export function SeverityBadge({ severity }: Readonly<{ severity: "low" | "moderate" | "high" | "critical" }>) {
  return <span className={`severity-badge severity-badge--${severity}`}>{severity}</span>;
}

export function ClaimVerification({ status }: Readonly<{ status: "supported" | "partially supported" | "unsupported" | "contradicted" | "unverifiable" }>) {
  return <span className={`verification verification--${status.replace(" ", "-")}`}>{status}</span>;
}

export function PeriodLabel({ basis }: Readonly<{ basis: PeriodBasis }>) {
  const labels: Record<PeriodBasis, string> = { instant: "Instant", annual: "Annual", quarterly: "Quarter", year_to_date: "Year to date" };
  return <span className="period-label">{labels[basis]}</span>;
}
