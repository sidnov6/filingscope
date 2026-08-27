from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from filingscope.schemas import (
    ComputationStatus,
    FinancialPeriod,
    ForensicTestResult,
    MetricResult,
)

TEST_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class TestDefinition:
    test_id: str
    category: str
    metric_id: str
    purpose: str
    evidence_requirements: tuple[str, ...]


TEST_DEFINITIONS = (
    TestDefinition(
        "receivables_growth_vs_revenue",
        "revenue_quality",
        "receivables_to_revenue",
        "Receivables intensity observation",
        ("Item 7 revenue and receivables discussion",),
    ),
    TestDefinition(
        "days_sales_outstanding_trend",
        "revenue_quality",
        "receivables_to_revenue",
        "Receivables-to-revenue basis for DSO review",
        ("Item 8 receivables policy",),
    ),
    TestDefinition(
        "contract_assets_review",
        "revenue_quality",
        "contract_assets_to_revenue",
        "Contract asset intensity",
        ("Item 8 revenue recognition note",),
    ),
    TestDefinition(
        "deferred_revenue_behavior",
        "revenue_quality",
        "deferred_revenue_to_revenue",
        "Deferred revenue intensity",
        ("Item 8 contract liabilities note",),
    ),
    TestDefinition(
        "cash_collections_proxy",
        "revenue_quality",
        "cfo_to_revenue",
        "Operating cash flow relative to revenue",
        ("Item 7 cash flow discussion",),
    ),
    TestDefinition(
        "cfo_vs_net_income",
        "earnings_quality",
        "cfo_to_net_income",
        "Cash conversion of reported earnings",
        ("Item 7 cash flows",),
    ),
    TestDefinition(
        "accrual_ratio",
        "earnings_quality",
        "accrual_ratio",
        "Accruals relative to assets",
        ("Item 7 operating results", "Item 8 cash flow statement"),
    ),
    TestDefinition(
        "free_cash_flow_conversion",
        "earnings_quality",
        "fcf_conversion",
        "Free cash flow relative to net income",
        ("Item 7 liquidity",),
    ),
    TestDefinition(
        "cfo_to_operating_income",
        "earnings_quality",
        "cfo_to_operating_income",
        "Operating cash flow relative to operating income",
        ("Item 7 cash flows",),
    ),
    TestDefinition(
        "noncash_adjustment_recurrence",
        "earnings_quality",
        "stock_compensation_to_revenue",
        "Recurring stock compensation observation",
        ("Item 8 stock compensation note",),
    ),
    TestDefinition(
        "inventory_growth_vs_sales",
        "working_capital",
        "inventory_to_revenue",
        "Inventory intensity",
        ("Item 7 inventory discussion",),
    ),
    TestDefinition(
        "days_inventory_outstanding",
        "working_capital",
        "inventory_to_revenue",
        "Inventory-to-revenue basis for DIO review",
        ("Item 8 inventory policy",),
    ),
    TestDefinition(
        "days_payables_outstanding",
        "working_capital",
        "payables_to_revenue",
        "Payables-to-revenue basis for DPO review",
        ("Item 7 working capital",),
    ),
    TestDefinition(
        "working_capital_intensity",
        "working_capital",
        "working_capital_intensity",
        "Working capital relative to revenue",
        ("Item 7 liquidity",),
    ),
    TestDefinition(
        "current_asset_composition",
        "working_capital",
        "current_ratio",
        "Current asset and liability coverage",
        ("Item 8 balance sheet notes",),
    ),
    TestDefinition(
        "gross_margin_volatility",
        "margins_costs",
        "gross_margin",
        "Gross margin history",
        ("Item 7 gross margin discussion",),
    ),
    TestDefinition(
        "operating_margin_divergence",
        "margins_costs",
        "operating_margin",
        "Operating margin history",
        ("Item 7 operating expenses",),
    ),
    TestDefinition(
        "selling_general_administrative_intensity",
        "margins_costs",
        "selling_general_administrative_to_revenue",
        "SG&A relative to revenue",
        ("Item 7 operating expenses",),
    ),
    TestDefinition(
        "research_development_intensity",
        "margins_costs",
        "research_development_to_revenue",
        "R&D relative to revenue",
        ("Item 7 research and development",),
    ),
    TestDefinition(
        "effective_tax_rate",
        "margins_costs",
        "effective_tax_rate",
        "Tax expense relative to pretax income",
        ("Item 8 income taxes note",),
    ),
    TestDefinition(
        "debt_to_equity",
        "balance_sheet",
        "debt_to_equity",
        "Debt relative to equity",
        ("Item 7 liquidity", "Item 8 debt note"),
    ),
    TestDefinition(
        "liabilities_to_assets",
        "balance_sheet",
        "liabilities_to_assets",
        "Liabilities relative to assets",
        ("Item 8 balance sheet",),
    ),
    TestDefinition(
        "goodwill_to_assets",
        "balance_sheet",
        "goodwill_to_assets",
        "Goodwill relative to assets",
        ("Item 8 goodwill note",),
    ),
    TestDefinition(
        "liquidity_deterioration",
        "balance_sheet",
        "current_ratio",
        "Current ratio history",
        ("Item 7 liquidity",),
    ),
    TestDefinition(
        "capital_expenditure_intensity",
        "balance_sheet",
        "capital_expenditure_to_revenue",
        "Capital expenditure relative to revenue",
        ("Item 7 capital resources",),
    ),
    TestDefinition(
        "stock_compensation_to_revenue",
        "dilution",
        "stock_compensation_to_revenue",
        "Stock compensation relative to revenue",
        ("Item 8 stock compensation note",),
    ),
    TestDefinition(
        "stock_compensation_to_fcf",
        "dilution",
        "stock_compensation_to_fcf",
        "Stock compensation relative to free cash flow",
        ("Item 8 stock compensation note",),
    ),
    TestDefinition(
        "diluted_share_spread",
        "dilution",
        "dilution_spread",
        "Diluted share count relative to basic shares",
        ("Item 8 earnings per share note",),
    ),
    TestDefinition(
        "buybacks_relative_to_stock_compensation",
        "dilution",
        "buybacks_to_stock_compensation",
        "Repurchases relative to stock compensation",
        ("Item 8 equity note",),
    ),
    TestDefinition(
        "beneish_m_score",
        "composite",
        "beneish_m_score",
        "Published composite screen; applicability required",
        ("Item 8 financial statements",),
    ),
    TestDefinition(
        "piotroski_f_score",
        "composite",
        "piotroski_f_score",
        "Published composite screen; applicability required",
        ("Item 8 financial statements",),
    ),
    TestDefinition(
        "altman_z_score",
        "composite",
        "altman_z_score",
        "Published composite screen; applicability required",
        ("Item 8 financial statements",),
    ),
)


class ForensicEngine:
    def __init__(self, definitions: tuple[TestDefinition, ...] = TEST_DEFINITIONS) -> None:
        self.definitions = definitions

    def run(self, metrics: Sequence[MetricResult]) -> tuple[ForensicTestResult, ...]:
        if not metrics:
            return ()
        fallback_period = max(metrics, key=_result_order).period
        results = [
            self._run_one(definition, metrics, fallback_period) for definition in self.definitions
        ]
        return tuple(sorted(results, key=lambda result: result.test_id))

    @staticmethod
    def _run_one(
        definition: TestDefinition,
        metrics: Sequence[MetricResult],
        fallback_period: FinancialPeriod,
    ) -> ForensicTestResult:
        candidates = [metric for metric in metrics if metric.metric_id == definition.metric_id]
        selected = max(candidates, key=_result_order) if candidates else None
        period = selected.period if selected else fallback_period
        result_id = _stable_id(
            TEST_VERSION,
            definition.test_id,
            period.start_date.isoformat() if period.start_date else "",
            period.end_date.isoformat(),
            selected.metric_result_id if selected else "missing",
        )
        context = {
            "category": definition.category,
            "metric_id": definition.metric_id,
            "purpose": definition.purpose,
            "evidence_requirements": list(definition.evidence_requirements),
            "screening_threshold": None,
        }
        if selected is None or selected.status == ComputationStatus.NOT_COMPUTABLE:
            reason = (
                selected.not_computable_reason
                if selected and selected.not_computable_reason
                else f"Required metric {definition.metric_id} is unavailable"
            )
            return ForensicTestResult(
                test_result_id=result_id,
                test_id=definition.test_id,
                test_version=TEST_VERSION,
                period=period,
                status=ComputationStatus.NOT_COMPUTABLE,
                threshold_context=context,
                metric_result_ids=(selected.metric_result_id,) if selected else (),
                data_confidence=selected.data_confidence if selected else None,
                reason=reason,
            )
        return ForensicTestResult(
            test_result_id=result_id,
            test_id=definition.test_id,
            test_version=TEST_VERSION,
            period=period,
            status=ComputationStatus.COMPUTED,
            result=selected.value,
            threshold_context=context,
            metric_result_ids=(selected.metric_result_id,),
            data_confidence=selected.data_confidence,
            reason=(
                "Deterministic diagnostic value only; no risk conclusion is assigned "
                "without a versioned anomaly or applicability rule."
            ),
        )


def _result_order(result: MetricResult) -> tuple[object, ...]:
    return (
        result.period.end_date,
        result.period.start_date or result.period.end_date,
        result.metric_result_id,
    )


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
