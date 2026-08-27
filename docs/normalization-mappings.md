# Canonical XBRL normalization mappings

Mapping version: `1.0.0`

The initial normalization registry is intentionally explicit. A raw fact is normalized only when its
taxonomy and concept exactly match a reviewed entry below. Unknown concepts remain unresolved and
produce a data-quality finding; the engine never guesses an alias or substitutes zero for a missing
value.

| Canonical metric | Exact source concept | Unit | Period type | Priority | Confidence |
| --- | --- | --- | --- | ---: | ---: |
| `assets` | `us-gaap:Assets` | USD | instant | 1 | 1.0 |
| `revenue` | `us-gaap:Revenues` | USD | duration | 1 | 1.0 |
| `net_income` | `us-gaap:NetIncomeLoss` | USD | duration | 1 | 1.0 |
| `cost_of_revenue` | `us-gaap:CostOfRevenue` | USD | duration | 1 | 1.0 |
| `gross_profit` | `us-gaap:GrossProfit` | USD | duration | 1 | 1.0 |
| `operating_income` | `us-gaap:OperatingIncomeLoss` | USD | duration | 1 | 1.0 |
| `selling_general_administrative` | `us-gaap:SellingGeneralAndAdministrativeExpense` | USD | duration | 1 | 1.0 |
| `research_development` | `us-gaap:ResearchAndDevelopmentExpense` | USD | duration | 1 | 1.0 |
| `interest_expense` | `us-gaap:InterestExpenseNonoperating` | USD | duration | 1 | 1.0 |
| `income_tax_expense` | `us-gaap:IncomeTaxExpenseBenefit` | USD | duration | 1 | 1.0 |
| `pretax_income` | `us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` | USD | duration | 1 | 1.0 |
| `cash` | `us-gaap:CashAndCashEquivalentsAtCarryingValue` | USD | instant | 1 | 1.0 |
| `receivables` | `us-gaap:AccountsReceivableNetCurrent` | USD | instant | 1 | 1.0 |
| `inventory` | `us-gaap:InventoryNet` | USD | instant | 1 | 1.0 |
| `current_assets` | `us-gaap:AssetsCurrent` | USD | instant | 1 | 1.0 |
| `current_liabilities` | `us-gaap:LiabilitiesCurrent` | USD | instant | 1 | 1.0 |
| `property_plant_equipment` | `us-gaap:PropertyPlantAndEquipmentNet` | USD | instant | 1 | 1.0 |
| `goodwill` | `us-gaap:Goodwill` | USD | instant | 1 | 1.0 |
| `accounts_payable` | `us-gaap:AccountsPayableCurrent` | USD | instant | 1 | 1.0 |
| `debt` | `us-gaap:LongTermDebt` | USD | instant | 1 | 1.0 |
| `liabilities` | `us-gaap:Liabilities` | USD | instant | 1 | 1.0 |
| `equity` | `us-gaap:StockholdersEquity` | USD | instant | 1 | 1.0 |
| `operating_cash_flow` | `us-gaap:NetCashProvidedByUsedInOperatingActivities` | USD | duration | 1 | 1.0 |
| `capital_expenditure` | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | USD | duration | 1 | 1.0 |
| `acquisitions` | `us-gaap:PaymentsToAcquireBusinessesNetOfCashAcquired` | USD | duration | 1 | 1.0 |
| `share_repurchases` | `us-gaap:PaymentsForRepurchaseOfCommonStock` | USD | duration | 1 | 1.0 |
| `dividends` | `us-gaap:PaymentsOfDividends` | USD | duration | 1 | 1.0 |
| `stock_based_compensation` | `us-gaap:ShareBasedCompensation` | USD | duration | 1 | 1.0 |
| `basic_shares` | `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic` | shares | duration | 1 | 1.0 |
| `diluted_shares` | `us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding` | shares | duration | 1 | 1.0 |
| `common_shares_outstanding` | `us-gaap:CommonStockSharesOutstanding` | shares | instant | 1 | 1.0 |

The concept types and period types were reviewed against the FASB 2026 US GAAP taxonomy
[schema](https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-2026.xsd) and
[documentation labels](https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-doc-2026.xml). The SEC
[EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
defines Company Facts as entity-wide, standardized taxonomy facts grouped by unit and describes the
annual, quarterly, and instant frame semantics used here.

## Period classification

- Instant facts are classified as `instant`; a duration fact carrying an instant SEC frame is
  rejected.
- `CY####` duration frames are `annual`.
- `CY####Q#` duration frames are `quarterly`.
- If a duration fact has no usable frame, 335–395 inclusive days is annual and 61–121 inclusive
  days is quarterly, matching the SEC's documented 365 ± 30 and 91 ± 30 windows.
- A frame-less Q2 or Q3 duration of 122–304 days is `year_to_date`.
- Every other duration is preserved as `other_duration`, not silently forced into a standard period.

The default period filter includes instant, annual, and quarterly facts. Year-to-date facts require
an explicit filter choice so a cumulative value cannot be mistaken for a standalone quarter.

## Duplicate and amendment selection

Facts compete only within the same canonical metric, unit, start/end dates, fiscal year/period, and
classified reporting basis. Selection order is deterministic:

1. Explicit target-accession order, when supplied.
2. Concept priority from the mapping registry.
3. Original filing by default, or amendment when `prefer_amendments` is explicitly enabled.
4. Most recent filing date, then accession number.

Each selected fact retains its original fact ID, taxonomy concept, accession, form, filing date,
frame, source manifest, mapping version, confidence, and human-readable selection rationale.

## Current boundary

This version does not map extension concepts, infer calculation relationships, normalize currencies,
or derive quarterly values from year-to-date facts. Exact US GAAP concepts that are not present in
the recorded fixture correctly produce missing-metric findings. Derived financial formulas are
separately versioned and documented in `docs/deterministic-analysis.md`.
