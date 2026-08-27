"use client";

import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type SortingState } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type { FinancialFact } from "../data/workspace";
import { DataQualityBadge, MetricValue, PeriodLabel } from "./DomainComponents";

export function FinancialTable({ facts }: Readonly<{ facts: FinancialFact[] }>) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "endDate", desc: true }]);
  const columns = useMemo(() => [
    { accessorKey: "metric", header: "Metric", cell: (info: { getValue: () => unknown }) => <strong>{String(info.getValue())}</strong> },
    { accessorKey: "endDate", header: "Period end" },
    { accessorKey: "basis", header: "Basis", cell: (info: { getValue: () => unknown }) => <PeriodLabel basis={info.getValue() as FinancialFact["basis"]} /> },
    { accessorKey: "value", header: "Reported value", cell: (info: { row: { original: FinancialFact } }) => <MetricValue value={info.row.original.value} unit={info.row.original.unit} /> },
    { accessorKey: "concept", header: "Source concept", cell: (info: { getValue: () => unknown }) => <code>{String(info.getValue())}</code> },
    { accessorKey: "accession", header: "Accession", cell: (info: { getValue: () => unknown }) => <span className="mono">{String(info.getValue())}</span> },
    { accessorKey: "confidence", header: "Quality", cell: () => <DataQualityBadge state="verified">Exact map</DataQualityBadge> },
  ], []);
  // TanStack Table intentionally exposes non-memoizable functions through its table instance.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data: facts, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  return (
    <div className="table-wrap" role="region" aria-label="Normalized financial facts" tabIndex={0}>
      <table>
        <thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id} scope="col" aria-sort={header.column.getIsSorted() === "asc" ? "ascending" : header.column.getIsSorted() === "desc" ? "descending" : "none"}><button className="table-sort" onClick={header.column.getToggleSortingHandler()}>{flexRender(header.column.columnDef.header, header.getContext())}</button></th>)}</tr>)}</thead>
        <tbody>{table.getRowModel().rows.map((row) => <tr key={row.id}>{row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
