export type PeriodBasis = "instant" | "annual" | "quarterly" | "year_to_date";

export type Company = { name: string; ticker: string; cik: string };
export type CompanySearchResult = Company & { locallyAvailable: boolean };
export type FinancialFact = { id: string; metric: string; value: number; unit: string; endDate: string; basis: PeriodBasis; accession: string; concept: string; confidence: number };
export type EvidenceItem = { id: string; section: string; accession: string; excerpt: string; sourceUrl: string };
export type GeographicLocation = { id: string; label: string; latitude: number; longitude: number; address: string; precision: "administrative_area_centroid"; sourceUrl: string; sourceHash: string; limitation: string };
export type FilingItem = { accession: string; form: string; filingDate: string; reportPeriod?: string };

export type WorkspaceData = {
  source: "api" | "recorded-fixture";
  company: Company;
  facts: FinancialFact[];
  factCount: number;
  filings: FilingItem[];
  filingCount: number;
  quality: { findings: number; missingMetrics: number; mappingVersion: string };
  analytics: { metricResults: number; forensicTests: number; computableTests: number };
  signals: Array<{ id: string; test: string; category: string; severity: "low" | "moderate" | "high" | "critical"; score: number; reason: string }>;
  evidence: EvidenceItem[];
  geography: { locations: GeographicLocation[]; notice: string };
  refreshedAt: string;
  error?: string;
};

export const recordedFixture: WorkspaceData = {
  source: "recorded-fixture",
  company: { name: "Apple Inc.", ticker: "AAPL", cik: "0000320193" },
  facts: [
    { id: "asset-q2", metric: "Assets", value: 371082000000, unit: "USD", endDate: "2026-03-28", basis: "instant", accession: "0000320193-26-000013", concept: "us-gaap:Assets", confidence: 1 },
    { id: "asset-q3", metric: "Assets", value: 383266000000, unit: "USD", endDate: "2026-06-27", basis: "instant", accession: "0000320193-26-000020", concept: "us-gaap:Assets", confidence: 1 },
    { id: "net-ytd", metric: "Net income", value: 101464000000, unit: "USD", endDate: "2026-06-27", basis: "year_to_date", accession: "0000320193-26-000020", concept: "us-gaap:NetIncomeLoss", confidence: 1 },
    { id: "net-q3", metric: "Net income", value: 29789000000, unit: "USD", endDate: "2026-06-27", basis: "quarterly", accession: "0000320193-26-000020", concept: "us-gaap:NetIncomeLoss", confidence: 1 },
    { id: "revenue-fy", metric: "Revenue", value: 265595000000, unit: "USD", endDate: "2018-09-29", basis: "annual", accession: "0000320193-18-000145", concept: "us-gaap:Revenues", confidence: 1 },
    { id: "revenue-q4", metric: "Revenue", value: 62900000000, unit: "USD", endDate: "2018-09-29", basis: "quarterly", accession: "0000320193-18-000145", concept: "us-gaap:Revenues", confidence: 1 },
  ],
  factCount: 6,
  filings: [
    { accession: "0000320193-26-000020", form: "10-Q", filingDate: "2026-07-31", reportPeriod: "2026-06-27" },
    { accession: "0000320193-26-000018", form: "8-K", filingDate: "2026-07-30", reportPeriod: "2026-07-30" },
    { accession: "0000320193-26-000013", form: "10-Q", filingDate: "2026-05-01", reportPeriod: "2026-03-28" },
    { accession: "0000320193-26-000011", form: "8-K", filingDate: "2026-04-30", reportPeriod: "2026-04-30" },
  ],
  filingCount: 4,
  quality: { findings: 29, missingMetrics: 28, mappingVersion: "1.0.0" },
  analytics: { metricResults: 10, forensicTests: 32, computableTests: 0 },
  signals: [],
  evidence: [{ id: "E-RECORDED-2018", section: "Item 9A", accession: "0000320193-18-000145", excerpt: "Management concluded that internal control over financial reporting was effective as of September 29, 2018.", sourceUrl: "https://www.sec.gov/Archives/edgar/data/320193/000032019318000145/a10-k20189292018.htm" }],
  geography: {
    locations: [{ id: "apple-business-address-ca", label: "Registered business address · Cupertino", latitude: 36.1162, longitude: -119.6816, address: "ONE APPLE PARK WAY, CUPERTINO, CA, 95014", precision: "administrative_area_centroid", sourceUrl: "https://www.sec.gov/Archives/edgar/data/320193/000114036126023149/0001140361-26-023149-index.htm", sourceHash: "recorded-sec-source", limitation: "Marker is the California centroid for orientation, not the office coordinate and not evidence of operating or revenue exposure." }],
    notice: "Only SEC-sourced registered-address context is shown. Markers do not represent revenue, assets, suppliers, customers, or operating exposure.",
  },
  refreshedAt: "2026-08-27T00:00:00Z",
};

type ApiFinancials = { company: { legal_name: string; cik: string; tickers: string[] }; facts: Array<{ normalized_fact_id: string; canonical_metric: string; value: string; unit: string; period: { end_date: string; reporting_basis: PeriodBasis }; accession_number: string; original_taxonomy: string; original_concept: string; data_confidence: string; mapping_version: string }>; normalized_fact_count: number; filings: Array<{ accession_number: string; form: string; filing_date: string; report_period?: string }>; filing_count: number; finding_count: number; missing_metric_count: number };
type ApiSignals = { metric_count: number; tests: Array<{ status: string }>; signals: Array<{ signal_id: string; test_id: string; category: string; severity: "low" | "moderate" | "high" | "critical"; score: string; score_explanation: string }> };

export async function fetchWorkspace(cik: string): Promise<WorkspaceData> {
  const [financialResponse, signalResponse, evidenceResponse, geographyResponse] = await Promise.all([
    fetch(`/companies/${cik}/financials`, { cache: "no-store" }),
    fetch(`/companies/${cik}/signals`, { cache: "no-store" }),
    fetch(`/companies/${cik}/evidence`, { cache: "no-store" }),
    fetch(`/companies/${cik}/geography`, { cache: "no-store" }),
  ]);
  if (!financialResponse.ok || !signalResponse.ok) throw new Error("Prepared company data could not be loaded.");
  const financials = (await financialResponse.json()) as ApiFinancials;
  const analytics = (await signalResponse.json()) as ApiSignals;
  const evidencePayload = evidenceResponse.ok ? await evidenceResponse.json() as { evidence: Array<{ evidence_id: string; section: string; excerpt: string; source: { accession_number?: string; source_url: string } }> } : { evidence: [] };
  const geographyPayload = geographyResponse.ok ? await geographyResponse.json() as { locations: Array<{ geographic_evidence_id: string; label: string; latitude: number; longitude: number; address: string; precision: "administrative_area_centroid"; source_url: string; source_sha256: string; limitation: string }>; notice: string } : { locations: [], notice: "No sourced geographic context is available for this company." };
  const fallbackEvidence = financials.company.cik === recordedFixture.company.cik ? recordedFixture.evidence : [];
  return {
    source: "api",
    company: { name: financials.company.legal_name, ticker: financials.company.tickers[0] ?? "—", cik: financials.company.cik },
    facts: financials.facts.map((fact) => ({ id: fact.normalized_fact_id, metric: fact.canonical_metric.replaceAll("_", " "), value: Number(fact.value), unit: fact.unit, endDate: fact.period.end_date, basis: fact.period.reporting_basis, accession: fact.accession_number, concept: `${fact.original_taxonomy}:${fact.original_concept}`, confidence: Number(fact.data_confidence) })),
    factCount: financials.normalized_fact_count,
    filings: financials.filings.map((filing) => ({ accession: filing.accession_number, form: filing.form, filingDate: filing.filing_date, reportPeriod: filing.report_period })),
    filingCount: financials.filing_count,
    quality: { findings: financials.finding_count, missingMetrics: financials.missing_metric_count, mappingVersion: financials.facts[0]?.mapping_version ?? "1.0.0" },
    analytics: { metricResults: analytics.metric_count, forensicTests: analytics.tests.length, computableTests: analytics.tests.filter((test) => test.status === "computed").length },
    signals: analytics.signals.map((signal) => ({ id: signal.signal_id, test: signal.test_id, category: signal.category, severity: signal.severity, score: Number(signal.score), reason: signal.score_explanation })),
    evidence: evidencePayload.evidence.length ? evidencePayload.evidence.map((item) => ({ id: item.evidence_id, section: item.section, accession: item.source.accession_number ?? "—", excerpt: item.excerpt, sourceUrl: item.source.source_url })) : fallbackEvidence,
    geography: { locations: geographyPayload.locations.map((location) => ({ id: location.geographic_evidence_id, label: location.label, latitude: location.latitude, longitude: location.longitude, address: location.address, precision: location.precision, sourceUrl: location.source_url, sourceHash: location.source_sha256, limitation: location.limitation })), notice: geographyPayload.notice },
    refreshedAt: new Date().toISOString(),
  };
}
