"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { CompanySearchResult } from "../data/workspace";
import { useWorkspace } from "./WorkspaceProvider";

export function CompanySearch() {
  const { selectCompany, status } = useWorkspace();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CompanySearchResult[]>([]);
  const [notice, setNotice] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const sequence = useRef(0);
  const suppressNextSearch = useRef(false);

  useEffect(() => {
    if (suppressNextSearch.current) {
      suppressNextSearch.current = false;
      return;
    }
    const trimmed = query.trim();
    if (trimmed.length < 2 && !/^\d+$/.test(trimmed)) {
      return;
    }
    const request = ++sequence.current;
    const timeout = window.setTimeout(async () => {
      try {
        const response = await fetch(`/companies/search?q=${encodeURIComponent(trimmed)}&limit=10`, { cache: "no-store" });
        if (!response.ok) throw new Error("Search service unavailable");
        const payload = await response.json() as { results: Array<{ cik: string; ticker: string; legal_name: string; locally_available: boolean }>; notice?: string };
        if (request !== sequence.current) return;
        setResults(payload.results.map((item) => ({ cik: item.cik, ticker: item.ticker, name: item.legal_name, locallyAvailable: item.locally_available })));
        setNotice(payload.notice ?? "Official SEC company directory");
        setActive(0);
        setOpen(true);
      } catch {
        if (request !== sequence.current) return;
        setResults([]);
        setNotice("Company search is temporarily unavailable.");
        setOpen(true);
      }
    }, 220);
    return () => window.clearTimeout(timeout);
  }, [query]);

  async function choose(result: CompanySearchResult) {
    suppressNextSearch.current = true;
    setQuery(`${result.ticker} · ${result.name}`);
    setOpen(false);
    await selectCompany(result);
  }

  return (
    <div className="company-search">
      <label htmlFor="company-search-input">Search any SEC company</label>
      <div className="search-control">
        <span aria-hidden="true">⌕</span>
        <input
          id="company-search-input"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open && results[active] ? `${listId}-${active}` : undefined}
          value={query}
          placeholder="Ticker, company name, or CIK"
          autoComplete="off"
          onChange={(event) => {
            const next = event.target.value;
            setQuery(next);
            if (next.trim().length < 2 && !/^\d+$/.test(next.trim())) setOpen(false);
          }}
          onFocus={() => results.length && setOpen(true)}
          onKeyDown={(event) => {
            if (!open) return;
            if (event.key === "ArrowDown") { event.preventDefault(); setActive((value) => Math.min(value + 1, results.length - 1)); }
            if (event.key === "ArrowUp") { event.preventDefault(); setActive((value) => Math.max(value - 1, 0)); }
            if (event.key === "Escape") setOpen(false);
            if (event.key === "Enter" && results[active]) { event.preventDefault(); void choose(results[active]); }
          }}
        />
        {status === "preparing" ? <span className="search-spinner" aria-label="Preparing company" /> : <kbd>⌘ K</kbd>}
      </div>
      {open ? (
        <div className="search-results" id={listId} role="listbox" aria-label="SEC company matches">
          {results.map((result, index) => (
            <button
              id={`${listId}-${index}`}
              key={result.cik}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onClick={() => void choose(result)}
            >
              <strong>{result.ticker}</strong>
              <span>{result.name}</span>
              <small>CIK {result.cik} · {result.locallyAvailable ? "prepared" : "fetch from SEC"}</small>
            </button>
          ))}
          {!results.length ? <p>No matching prepared company.</p> : null}
          <footer>{notice}</footer>
        </div>
      ) : null}
    </div>
  );
}
