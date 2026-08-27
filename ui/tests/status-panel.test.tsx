import { SaltProvider } from "@salt-ds/core";
import { fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";

import { AppShell } from "../src/components/AppShell";
import { DataQualityBadge, MetricValue, PeriodLabel } from "../src/components/DomainComponents";
import { FinancialTable } from "../src/components/FinancialTable";
import { Overview } from "../src/components/Overview";
import { StatusPanel } from "../src/components/StatusPanel";
import { WorkspaceProvider } from "../src/components/WorkspaceProvider";

describe("StatusPanel", () => {
  it.each(["empty", "partial", "stale", "error"] as const)(
    "announces the %s state with a labelled region",
    (state) => {
      render(
        <SaltProvider>
          <StatusPanel state={state} title="Fixture state" detail="Actionable detail" />
        </SaltProvider>,
      );
      expect(screen.getByLabelText(new RegExp(`Fixture state`, "i"))).toBeInTheDocument();
      expect(screen.getByText("Actionable detail")).toBeVisible();
    },
  );

  it("exposes loading semantics without flashing fake content", () => {
    render(<StatusPanel state="loading" title="Loading submissions" />);
    expect(screen.getByLabelText("Loading submissions")).toHaveAttribute("aria-busy", "true");
  });
});

describe("AppShell", () => {
  it("has an accessible skip link, navigation label, and pressed density control", () => {
    render(
      <SaltProvider>
        <WorkspaceProvider><AppShell><p>Content</p></AppShell></WorkspaceProvider>
      </SaltProvider>,
    );
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("navigation", { name: "Research workspace" })).toBeVisible();
    const density = screen.getByRole("button", { name: "Compact density" });
    expect(density).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(density);
    expect(screen.getByRole("button", { name: "Comfortable density" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("has no automated WCAG 2.2 A/AA violations in the overview shell", async () => {
    render(
      <SaltProvider>
        <WorkspaceProvider><AppShell><Overview /></AppShell></WorkspaceProvider>
      </SaltProvider>,
    );
    const result = await axe.run(document.body, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] },
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});

describe("Financial workstation components", () => {
  it("shows unit, period basis, provenance, and non-color quality text", () => {
    render(
      <FinancialTable
        facts={[{
          id: "fact-1",
          metric: "Revenue",
          value: 265595000000,
          unit: "USD",
          endDate: "2018-09-29",
          basis: "annual",
          accession: "0000320193-18-000145",
          concept: "us-gaap:Revenues",
          confidence: 1,
        }]}
      />,
    );
    expect(screen.getByRole("region", { name: "Normalized financial facts" })).toBeVisible();
    expect(screen.getByText("Annual")).toBeVisible();
    expect(screen.getByText("Exact map")).toBeVisible();
    expect(screen.getByText("us-gaap:Revenues")).toBeVisible();
  });

  it("formats values and semantic labels without color-only meaning", () => {
    render(<div><MetricValue value={1200000000} /><DataQualityBadge state="partial">Partial</DataQualityBadge><PeriodLabel basis="year_to_date" /></div>);
    expect(screen.getByText("1.2B")).toBeVisible();
    expect(screen.getByText("Partial")).toBeVisible();
    expect(screen.getByText("Year to date")).toBeVisible();
  });
});
