from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from filingscope.analytics import MetricEngine
from filingscope.forensics import AnomalyEngine, ForensicEngine, SignalEngine
from filingscope.forensics.engine import TEST_DEFINITIONS
from filingscope.schemas import (
    ComputationStatus,
    FinancialPeriod,
    NormalizedFinancialFact,
    PeriodBasis,
    SourceReference,
)


def _source() -> SourceReference:
    return SourceReference(
        source_type="sec_companyfacts",
        source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json",
        content_sha256="b" * 64,
        manifest_id="manifest-analytics",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _fact(metric: str, value: str, *, instant: bool = False) -> NormalizedFinancialFact:
    period = FinancialPeriod(
        period_type="instant" if instant else "duration",
        start_date=None if instant else date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        fiscal_year=2025,
        fiscal_period="FY",
        reporting_basis=PeriodBasis.INSTANT if instant else PeriodBasis.ANNUAL,
    )
    fact_id = f"normalized-{metric}-2025"
    return NormalizedFinancialFact(
        normalized_fact_id=fact_id,
        cik="0000000001",
        canonical_metric=metric,
        original_fact_id=f"original-{metric}-2025",
        original_taxonomy="us-gaap",
        original_concept=metric,
        value=Decimal(value),
        unit="shares" if "shares" in metric else "USD",
        period=period,
        form="10-K",
        filed=date(2026, 2, 1),
        accession_number="0000000001-26-000001",
        mapping_version="test",
        selection_rank=1,
        selection_rationale="Hand-reviewed formula fixture.",
        data_confidence=Decimal("1"),
        source=_source(),
    )


def _complete_facts() -> list[NormalizedFinancialFact]:
    durations = {
        "revenue": "100",
        "gross_profit": "40",
        "operating_income": "25",
        "net_income": "20",
        "operating_cash_flow": "30",
        "capital_expenditure": "10",
        "stock_based_compensation": "5",
        "research_development": "8",
        "selling_general_administrative": "10",
        "pretax_income": "25",
        "income_tax_expense": "5",
        "basic_shares": "100",
        "diluted_shares": "105",
        "share_repurchases": "8",
    }
    instants = {
        "assets": "200",
        "liabilities": "120",
        "current_assets": "80",
        "current_liabilities": "40",
        "equity": "80",
        "debt": "50",
        "goodwill": "20",
        "receivables": "15",
        "inventory": "10",
        "accounts_payable": "12",
    }
    return [
        *(_fact(metric, value) for metric, value in durations.items()),
        *(_fact(metric, value, instant=True) for metric, value in instants.items()),
    ]


def test_hand_calculated_formulas_and_25_test_registry() -> None:
    metrics = MetricEngine().calculate(_complete_facts())
    computed = {
        metric.metric_id: metric.value
        for metric in metrics
        if metric.status == ComputationStatus.COMPUTED
    }

    assert computed["free_cash_flow"] == Decimal("20")
    assert computed["net_margin"] == Decimal("0.2")
    assert computed["current_ratio"] == Decimal("2")
    assert computed["accrual_ratio"] == Decimal("-0.05")
    assert computed["dilution_spread"] == Decimal("0.05")
    assert len(TEST_DEFINITIONS) >= 25

    tests = ForensicEngine().run(metrics)
    assert len(tests) == len(TEST_DEFINITIONS)
    assert all(test.test_version == "1.0.0" for test in tests)
    assert any(test.status == ComputationStatus.COMPUTED for test in tests)
    assert any(test.status == ComputationStatus.NOT_COMPUTABLE for test in tests)


def test_zero_denominator_is_not_computable_not_zero() -> None:
    facts = [_fact("revenue", "0"), _fact("net_income", "20")]
    metrics = MetricEngine().calculate(facts)
    net_margin = next(metric for metric in metrics if metric.metric_id == "net_margin")

    assert net_margin.status == ComputationStatus.NOT_COMPUTABLE
    assert net_margin.value is None
    assert net_margin.not_computable_reason == "Formula denominator is zero"


def test_robust_anomaly_produces_explainable_screening_signal() -> None:
    facts: list[NormalizedFinancialFact] = []
    for year, value in [(2022, "10"), (2023, "11"), (2024, "9"), (2025, "30")]:
        fact = _fact("gross_profit", value).model_copy(
            update={
                "normalized_fact_id": f"normalized-gross-profit-{year}",
                "original_fact_id": f"original-gross-profit-{year}",
                "period": FinancialPeriod(
                    period_type="duration",
                    start_date=date(year, 1, 1),
                    end_date=date(year, 12, 31),
                    fiscal_year=year,
                    fiscal_period="FY",
                    reporting_basis=PeriodBasis.ANNUAL,
                ),
            }
        )
        revenue = _fact("revenue", "100").model_copy(
            update={
                "normalized_fact_id": f"normalized-revenue-{year}",
                "original_fact_id": f"original-revenue-{year}",
                "period": fact.period,
            }
        )
        facts.extend([fact, revenue])

    metrics = MetricEngine().calculate(facts)
    tests = ForensicEngine().run(metrics)
    anomalies = AnomalyEngine().analyze(metrics)
    signals = SignalEngine().rank(anomalies, tests)

    assert signals
    assert signals[0].severity == "moderate"
    assert "threshold 3.5" in signals[0].score_explanation
