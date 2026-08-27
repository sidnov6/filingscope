"use client";

import { ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

export function TrendChart({ points, label }: Readonly<{ points: Array<{ time: string; value: number }>; label: string }>) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current) return;
    const chart = createChart(host.current, { height: 220, layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#526172" }, grid: { vertLines: { color: "#eef2f5" }, horzLines: { color: "#eef2f5" } }, rightPriceScale: { borderColor: "#ccd5dc" }, timeScale: { borderColor: "#ccd5dc" } });
    const series = chart.addSeries(LineSeries, { color: "#087f7a", lineWidth: 2 });
    series.setData(points.map((point) => ({ time: Math.floor(new Date(point.time).getTime() / 1000) as UTCTimestamp, value: point.value / 1_000_000_000 })));
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(([entry]) => chart.applyOptions({ width: entry.contentRect.width }));
    observer.observe(host.current);
    return () => { observer.disconnect(); chart.remove(); };
  }, [points]);
  return (
    <section className="chart-panel" aria-labelledby="trend-title">
      <div className="section-heading"><div><p className="eyebrow">Reported trend</p><h2 id="trend-title">{label}</h2></div><p>USD billions · instant</p></div>
      <div ref={host} aria-hidden="true" />
      <table className="sr-only"><caption>{label} accessible data</caption><thead><tr><th>Date</th><th>USD</th></tr></thead><tbody>{points.map((point) => <tr key={point.time}><td>{point.time}</td><td>{point.value}</td></tr>)}</tbody></table>
    </section>
  );
}
