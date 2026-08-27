"use client";

import { Button } from "@salt-ds/core";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { CompanySearch } from "./CompanySearch";
import { useWorkspace } from "./WorkspaceProvider";

const navigation = [
  { label: "Overview", href: "/" },
  { label: "Financials", href: "/financials" },
  { label: "Signals", href: "/signals" },
  { label: "Investigation", href: "/investigation" },
  { label: "Evidence", href: "/evidence" },
  { label: "Geography", href: "/geography" },
  { label: "Audit", href: "/audit" },
];

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const [compact, setCompact] = useState(false);
  const pathname = usePathname();
  const { data, status, statusMessage, refresh } = useWorkspace();

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.getElementById("company-search-input")?.focus();
      }
    }
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  return (
    <div className="app-shell" data-density={compact ? "compact" : "comfortable"}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="topbar">
        <Link className="product-mark" aria-label="FilingScope home" href="/">
          <span className="product-symbol" aria-hidden="true">FS</span>
          <span>FilingScope<small>SEC intelligence</small></span>
        </Link>
        <CompanySearch />
        <div className="topbar-actions">
          <Button onClick={() => void refresh()} disabled={status === "loading" || status === "preparing"}>Refresh</Button>
          <Button onClick={() => setCompact((value) => !value)} aria-pressed={compact} aria-label={compact ? "Comfortable density" : "Compact density"}>{compact ? "Comfortable" : "Compact"}</Button>
        </div>
        <dl className="company-context" aria-label="Current research context">
          <div><dt>Selected company</dt><dd>{data.company.name}<span>{data.company.ticker} · CIK {data.company.cik}</span></dd></div>
          <div><dt>Coverage</dt><dd>{data.factCount} facts<span>{data.filingCount} filings · {data.analytics.forensicTests} tests</span></dd></div>
          <div><dt>Workspace state</dt><dd><span className={`status-dot status-dot--${status === "ready" ? "success" : "warning"}`} />{status === "preparing" ? "Preparing" : status === "loading" ? "Loading" : status === "error" ? "Attention" : "Ready"}<span>{statusMessage}</span></dd></div>
        </dl>
      </header>
      <div className="workspace">
        <nav className="left-nav" aria-label="Research workspace">
          <ul>{navigation.map((item) => <li key={item.label}><Link href={item.href} aria-current={pathname === item.href ? "page" : undefined}>{item.label}</Link></li>)}</ul>
          <div className="nav-footer"><span>Deterministic first</span><small>Evidence before agents</small><Link className="component-link" href="/components-explorer">Component states</Link></div>
        </nav>
        <main id="main-content" className="main-canvas" tabIndex={-1}>{children}</main>
      </div>
      <div className="sr-only" role="status" aria-live="polite">{statusMessage}</div>
    </div>
  );
}
