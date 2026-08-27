# Deterministic analytics and screening policy

Formula version: `1.0.0`  
Forensic-test version: `1.0.0`

The metric engine calculates outside prompts and retains every input fact ID, period, unit,
comparability flag, formula version, and minimum input confidence. A missing input or zero
denominator returns `not_computable`; it never returns zero as a substitute.

## Derived formulas

The versioned registry contains 24 transparent formulas:

- Free cash flow = operating cash flow − capital expenditure. The canonical capital-expenditure
  concept is a positive payment amount, so subtraction is explicit.
- Working capital = current assets − current liabilities.
- Gross, operating, and net margins divide the corresponding income measure by revenue.
- Cash conversion and accrual measures include CFO/net income,
  (net income − CFO)/assets, and FCF/net income.
- Liquidity and balance-sheet measures include current assets/current liabilities,
  liabilities/assets, debt/equity, and goodwill/assets.
- Working-capital intensity measures include receivables/revenue, inventory/revenue,
  payables/revenue, and working capital/revenue.
- Cost and dilution measures include SBC/revenue, SBC/FCF, R&D/revenue, SG&A/revenue,
  capex/revenue, effective tax rate, diluted-share spread, and buybacks/SBC.

Duration inputs must share start and end dates. Instant and duration inputs may align only when the
fiscal year, fiscal period, and end date match. This prevents unrelated periods from being combined.

## Forensic registry

The 32-test registry covers revenue quality, earnings quality, working capital, margins and costs,
balance sheet, dilution, and composite applicability. A test reports a deterministic diagnostic
value only when its source metric is computable. It deliberately contains no undisclosed company-risk
threshold. Beneish, Piotroski, and Altman entries remain `not_computable` until separately sourced
component formulas and applicability policies are added; their names alone never generate a score.

## Anomalies and signals

The anomaly engine reports current value, YoY/QoQ change when period basis supports it, historical
median, median absolute deviation, rolling percentile, sample count, and persistence. A robust
z-score requires at least four non-constant observations.

Signal policy version `1.0.0` uses the NIST-documented modified z-score form with the 0.67448975
scale and labels `|z| ≥ 3.5` as a potential outlier. FilingScope translates this only to a
`moderate` screening priority, never proof of misconduct. The score is an inspectable combination of
threshold distance and data confidence. See the
[NIST outlier guidance](https://itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).

## Quality and peers

The data-quality score reports completeness, unit consistency, mapping confidence, period alignment,
amendment status, and reconciliation separately. The overall score is the unweighted mean of the
five available components; reconciliation remains unavailable until sufficient statement coverage
exists.

Peer comparison requires an explicit `PeerPolicy`: minimum cohort size, minimum confidence, and
minimum/maximum asset-size ratios. Without that caller-reviewed policy or enough coherent SIC peers,
the result is `not_computable`. FilingScope does not invent peer thresholds.
