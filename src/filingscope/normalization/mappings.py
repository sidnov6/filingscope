from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

MAPPING_VERSION = "1.0.0"
TAXONOMY_SOURCE = "https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-2026.xsd"
TAXONOMY_DOCUMENTATION_SOURCE = "https://xbrl.fasb.org/us-gaap/2026/elts/us-gaap-doc-2026.xml"


@dataclass(frozen=True, slots=True)
class ConceptMapping:
    taxonomy: str
    concept: str
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class CanonicalMetricMapping:
    canonical_metric: str
    statement: Literal["income_statement", "balance_sheet", "cash_flow", "equity"]
    period_type: Literal["instant", "duration"]
    compatible_units: tuple[str, ...]
    concepts: tuple[ConceptMapping, ...]
    allowed_forms: tuple[str, ...] = ("10-K", "10-Q")
    taxonomy_year: int = 2026
    taxonomy_source: str = TAXONOMY_SOURCE
    documentation_source: str = TAXONOMY_DOCUMENTATION_SOURCE


class MappingRegistry:
    """Versioned, explicit mappings; concepts absent here remain unresolved."""

    version = MAPPING_VERSION

    def __init__(self, mappings: tuple[CanonicalMetricMapping, ...] | None = None) -> None:
        self.mappings = mappings or DEFAULT_MAPPINGS
        metrics = [mapping.canonical_metric for mapping in self.mappings]
        if len(metrics) != len(set(metrics)):
            raise ValueError("canonical metric mappings must be unique")

    def by_metric(self, metric: str) -> CanonicalMetricMapping:
        for mapping in self.mappings:
            if mapping.canonical_metric == metric:
                return mapping
        raise KeyError(metric)

    def concept_keys(self) -> frozenset[tuple[str, str]]:
        return frozenset(
            (concept.taxonomy, concept.concept)
            for mapping in self.mappings
            for concept in mapping.concepts
        )


DEFAULT_MAPPINGS = (
    CanonicalMetricMapping(
        canonical_metric="assets",
        statement="balance_sheet",
        period_type="instant",
        compatible_units=("USD",),
        concepts=(ConceptMapping("us-gaap", "Assets", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        canonical_metric="revenue",
        statement="income_statement",
        period_type="duration",
        compatible_units=("USD",),
        concepts=(ConceptMapping("us-gaap", "Revenues", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        canonical_metric="net_income",
        statement="income_statement",
        period_type="duration",
        compatible_units=("USD",),
        concepts=(ConceptMapping("us-gaap", "NetIncomeLoss", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "cost_of_revenue",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "CostOfRevenue", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "gross_profit",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "GrossProfit", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "operating_income",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "OperatingIncomeLoss", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "selling_general_administrative",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "SellingGeneralAndAdministrativeExpense", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "research_development",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "ResearchAndDevelopmentExpense", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "interest_expense",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "InterestExpenseNonoperating", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "income_tax_expense",
        "income_statement",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "IncomeTaxExpenseBenefit", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "pretax_income",
        "income_statement",
        "duration",
        ("USD",),
        (
            ConceptMapping(
                "us-gaap",
                "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                Decimal("1"),
            ),
        ),
    ),
    CanonicalMetricMapping(
        "cash",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "CashAndCashEquivalentsAtCarryingValue", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "receivables",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "AccountsReceivableNetCurrent", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "inventory",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "InventoryNet", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "current_assets",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "AssetsCurrent", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "current_liabilities",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "LiabilitiesCurrent", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "property_plant_equipment",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "PropertyPlantAndEquipmentNet", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "goodwill",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "Goodwill", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "accounts_payable",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "AccountsPayableCurrent", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "debt",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "LongTermDebt", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "liabilities",
        "balance_sheet",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "Liabilities", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "equity",
        "equity",
        "instant",
        ("USD",),
        (ConceptMapping("us-gaap", "StockholdersEquity", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "operating_cash_flow",
        "cash_flow",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "NetCashProvidedByUsedInOperatingActivities", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "capital_expenditure",
        "cash_flow",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "acquisitions",
        "cash_flow",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "PaymentsToAcquireBusinessesNetOfCashAcquired", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "share_repurchases",
        "cash_flow",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "PaymentsForRepurchaseOfCommonStock", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "dividends",
        "cash_flow",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "PaymentsOfDividends", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "stock_based_compensation",
        "equity",
        "duration",
        ("USD",),
        (ConceptMapping("us-gaap", "ShareBasedCompensation", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "basic_shares",
        "equity",
        "duration",
        ("shares",),
        (ConceptMapping("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic", Decimal("1")),),
    ),
    CanonicalMetricMapping(
        "diluted_shares",
        "equity",
        "duration",
        ("shares",),
        (
            ConceptMapping(
                "us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding", Decimal("1")
            ),
        ),
    ),
    CanonicalMetricMapping(
        "common_shares_outstanding",
        "equity",
        "instant",
        ("shares",),
        (ConceptMapping("us-gaap", "CommonStockSharesOutstanding", Decimal("1")),),
    ),
)
