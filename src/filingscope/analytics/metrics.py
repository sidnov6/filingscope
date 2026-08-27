from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation

from filingscope.schemas import (
    ComputationStatus,
    FinancialPeriod,
    MetricResult,
    NormalizedFinancialFact,
)

FORMULA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class FormulaDefinition:
    metric_id: str
    inputs: tuple[str, ...]
    unit: str
    expression: str
    calculate: Callable[[dict[str, Decimal]], Decimal]


def _ratio(numerator: str, denominator: str) -> Callable[[dict[str, Decimal]], Decimal]:
    return lambda values: values[numerator] / values[denominator]


FORMULAS = (
    FormulaDefinition(
        "free_cash_flow",
        ("operating_cash_flow", "capital_expenditure"),
        "USD",
        "operating_cash_flow - capital_expenditure",
        lambda values: values["operating_cash_flow"] - values["capital_expenditure"],
    ),
    FormulaDefinition(
        "working_capital",
        ("current_assets", "current_liabilities"),
        "USD",
        "current_assets - current_liabilities",
        lambda values: values["current_assets"] - values["current_liabilities"],
    ),
    FormulaDefinition(
        "gross_margin",
        ("gross_profit", "revenue"),
        "ratio",
        "gross_profit / revenue",
        _ratio("gross_profit", "revenue"),
    ),
    FormulaDefinition(
        "operating_margin",
        ("operating_income", "revenue"),
        "ratio",
        "operating_income / revenue",
        _ratio("operating_income", "revenue"),
    ),
    FormulaDefinition(
        "net_margin",
        ("net_income", "revenue"),
        "ratio",
        "net_income / revenue",
        _ratio("net_income", "revenue"),
    ),
    FormulaDefinition(
        "cfo_to_net_income",
        ("operating_cash_flow", "net_income"),
        "ratio",
        "operating_cash_flow / net_income",
        _ratio("operating_cash_flow", "net_income"),
    ),
    FormulaDefinition(
        "accrual_ratio",
        ("net_income", "operating_cash_flow", "assets"),
        "ratio",
        "(net_income - operating_cash_flow) / assets",
        lambda values: (values["net_income"] - values["operating_cash_flow"]) / values["assets"],
    ),
    FormulaDefinition(
        "fcf_conversion",
        ("free_cash_flow", "net_income"),
        "ratio",
        "free_cash_flow / net_income",
        _ratio("free_cash_flow", "net_income"),
    ),
    FormulaDefinition(
        "current_ratio",
        ("current_assets", "current_liabilities"),
        "ratio",
        "current_assets / current_liabilities",
        _ratio("current_assets", "current_liabilities"),
    ),
    FormulaDefinition(
        "liabilities_to_assets",
        ("liabilities", "assets"),
        "ratio",
        "liabilities / assets",
        _ratio("liabilities", "assets"),
    ),
    FormulaDefinition(
        "debt_to_equity",
        ("debt", "equity"),
        "ratio",
        "debt / equity",
        _ratio("debt", "equity"),
    ),
    FormulaDefinition(
        "goodwill_to_assets",
        ("goodwill", "assets"),
        "ratio",
        "goodwill / assets",
        _ratio("goodwill", "assets"),
    ),
    FormulaDefinition(
        "receivables_to_revenue",
        ("receivables", "revenue"),
        "ratio",
        "receivables / revenue",
        _ratio("receivables", "revenue"),
    ),
    FormulaDefinition(
        "inventory_to_revenue",
        ("inventory", "revenue"),
        "ratio",
        "inventory / revenue",
        _ratio("inventory", "revenue"),
    ),
    FormulaDefinition(
        "payables_to_revenue",
        ("accounts_payable", "revenue"),
        "ratio",
        "accounts_payable / revenue",
        _ratio("accounts_payable", "revenue"),
    ),
    FormulaDefinition(
        "working_capital_intensity",
        ("working_capital", "revenue"),
        "ratio",
        "working_capital / revenue",
        _ratio("working_capital", "revenue"),
    ),
    FormulaDefinition(
        "stock_compensation_to_revenue",
        ("stock_based_compensation", "revenue"),
        "ratio",
        "stock_based_compensation / revenue",
        _ratio("stock_based_compensation", "revenue"),
    ),
    FormulaDefinition(
        "stock_compensation_to_fcf",
        ("stock_based_compensation", "free_cash_flow"),
        "ratio",
        "stock_based_compensation / free_cash_flow",
        _ratio("stock_based_compensation", "free_cash_flow"),
    ),
    FormulaDefinition(
        "research_development_to_revenue",
        ("research_development", "revenue"),
        "ratio",
        "research_development / revenue",
        _ratio("research_development", "revenue"),
    ),
    FormulaDefinition(
        "selling_general_administrative_to_revenue",
        ("selling_general_administrative", "revenue"),
        "ratio",
        "selling_general_administrative / revenue",
        _ratio("selling_general_administrative", "revenue"),
    ),
    FormulaDefinition(
        "capital_expenditure_to_revenue",
        ("capital_expenditure", "revenue"),
        "ratio",
        "capital_expenditure / revenue",
        _ratio("capital_expenditure", "revenue"),
    ),
    FormulaDefinition(
        "effective_tax_rate",
        ("income_tax_expense", "pretax_income"),
        "ratio",
        "income_tax_expense / pretax_income",
        _ratio("income_tax_expense", "pretax_income"),
    ),
    FormulaDefinition(
        "dilution_spread",
        ("diluted_shares", "basic_shares"),
        "ratio",
        "(diluted_shares - basic_shares) / basic_shares",
        lambda values: (values["diluted_shares"] - values["basic_shares"]) / values["basic_shares"],
    ),
    FormulaDefinition(
        "buybacks_to_stock_compensation",
        ("share_repurchases", "stock_based_compensation"),
        "ratio",
        "share_repurchases / stock_based_compensation",
        _ratio("share_repurchases", "stock_based_compensation"),
    ),
)


class MetricEngine:
    def __init__(self, formulas: tuple[FormulaDefinition, ...] = FORMULAS) -> None:
        self.formulas = formulas

    def calculate(self, facts: Sequence[NormalizedFinancialFact]) -> tuple[MetricResult, ...]:
        results = [self._reported_result(fact) for fact in facts]
        for formula in self.formulas:
            available = [result for result in results if result.metric_id in formula.inputs]
            anchors = [result for result in available if result.metric_id == formula.inputs[0]]
            for anchor in anchors:
                inputs = self._aligned_inputs(anchor, available, formula.inputs)
                results.append(self._derived_result(formula, anchor.period, inputs))
        return tuple(sorted(results, key=self._sort_key))

    @staticmethod
    def _reported_result(fact: NormalizedFinancialFact) -> MetricResult:
        return MetricResult(
            metric_result_id=_stable_id("reported", fact.normalized_fact_id),
            metric_id=fact.canonical_metric,
            formula_version="reported:1.0.0",
            period=fact.period,
            status=ComputationStatus.COMPUTED,
            value=fact.value,
            unit=fact.unit,
            input_fact_ids=(fact.normalized_fact_id,),
            comparability_flags=(),
            data_confidence=fact.data_confidence,
        )

    @staticmethod
    def _aligned_inputs(
        anchor: MetricResult,
        candidates: Sequence[MetricResult],
        required: tuple[str, ...],
    ) -> dict[str, MetricResult]:
        inputs: dict[str, MetricResult] = {anchor.metric_id: anchor}
        for metric_id in required[1:]:
            matches = [
                candidate
                for candidate in candidates
                if candidate.metric_id == metric_id
                and _periods_align(anchor.period, candidate.period)
                and candidate.status == ComputationStatus.COMPUTED
            ]
            if matches:
                inputs[metric_id] = max(
                    matches,
                    key=lambda result: (
                        result.period.start_date or result.period.end_date,
                        result.metric_result_id,
                    ),
                )
        return inputs

    @staticmethod
    def _derived_result(
        formula: FormulaDefinition,
        period: FinancialPeriod,
        inputs: dict[str, MetricResult],
    ) -> MetricResult:
        missing = [metric for metric in formula.inputs if metric not in inputs]
        input_ids = tuple(
            sorted(fact_id for result in inputs.values() for fact_id in result.input_fact_ids)
        )
        result_id = _stable_id(
            FORMULA_VERSION,
            formula.metric_id,
            period.start_date.isoformat() if period.start_date else "",
            period.end_date.isoformat(),
            *input_ids,
        )
        if missing:
            return MetricResult(
                metric_result_id=result_id,
                metric_id=formula.metric_id,
                formula_version=FORMULA_VERSION,
                period=period,
                status=ComputationStatus.NOT_COMPUTABLE,
                input_fact_ids=input_ids,
                comparability_flags=("missing_inputs",),
                not_computable_reason=f"Missing required inputs: {', '.join(missing)}",
            )
        values: dict[str, Decimal] = {}
        for metric in formula.inputs:
            input_value = inputs[metric].value
            assert input_value is not None
            values[metric] = input_value
        try:
            value = formula.calculate(values)
        except (DivisionByZero, InvalidOperation, ZeroDivisionError):
            return MetricResult(
                metric_result_id=result_id,
                metric_id=formula.metric_id,
                formula_version=FORMULA_VERSION,
                period=period,
                status=ComputationStatus.NOT_COMPUTABLE,
                input_fact_ids=input_ids,
                comparability_flags=("zero_denominator",),
                not_computable_reason="Formula denominator is zero",
            )
        confidences = [
            result.data_confidence
            for result in inputs.values()
            if result.data_confidence is not None
        ]
        return MetricResult(
            metric_result_id=result_id,
            metric_id=formula.metric_id,
            formula_version=FORMULA_VERSION,
            period=period,
            status=ComputationStatus.COMPUTED,
            value=value,
            unit=formula.unit,
            input_fact_ids=input_ids,
            comparability_flags=(),
            data_confidence=min(confidences) if confidences else None,
        )

    @staticmethod
    def _sort_key(result: MetricResult) -> tuple[object, ...]:
        return (
            result.metric_id,
            result.period.end_date,
            result.period.start_date or result.period.end_date,
            result.metric_result_id,
        )


def _periods_align(left: FinancialPeriod, right: FinancialPeriod) -> bool:
    if left.end_date != right.end_date:
        return False
    if left.fiscal_year != right.fiscal_year or left.fiscal_period != right.fiscal_period:
        return False
    if left.period_type == right.period_type == "duration":
        return left.start_date == right.start_date
    return True


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
