from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from filingscope.normalization import Normalizer, PeriodFilter, SelectionPolicy, select_periods
from filingscope.normalization.periods import classify_period
from filingscope.schemas import FinancialPeriod, PeriodBasis, RawXbrlFact, SourceReference


def _source(accession: str = "0000000001-26-000001") -> SourceReference:
    return SourceReference(
        source_type="sec_companyfacts",
        source_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json",
        content_sha256="a" * 64,
        manifest_id="manifest-0001",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
        accession_number=accession,
    )


def _fact(
    *,
    fact_id: str = "fact-00000001",
    concept: str = "Revenues",
    unit: str = "USD",
    start: date | None = date(2025, 1, 1),
    end: date = date(2025, 12, 31),
    fiscal_period: str = "FY",
    form: str = "10-K",
    filed: date = date(2026, 2, 1),
    accession: str = "0000000001-26-000001",
    frame: str | None = "CY2025",
) -> RawXbrlFact:
    return RawXbrlFact(
        fact_id=fact_id,
        cik="0000000001",
        taxonomy="us-gaap",
        concept=concept,
        value=Decimal("42"),
        unit=unit,
        period=FinancialPeriod(
            period_type="duration" if start else "instant",
            start_date=start,
            end_date=end,
            fiscal_year=2025,
            fiscal_period=fiscal_period,
        ),
        form=form,
        filed=filed,
        accession_number=accession,
        frame=frame,
        source=_source(accession),
    )


@pytest.mark.parametrize(
    ("fact", "expected"),
    [
        (_fact(), PeriodBasis.ANNUAL),
        (
            _fact(
                start=date(2025, 7, 1),
                end=date(2025, 9, 30),
                fiscal_period="Q3",
                form="10-Q",
                frame="CY2025Q3",
            ),
            PeriodBasis.QUARTERLY,
        ),
        (
            _fact(
                start=date(2025, 1, 1),
                end=date(2025, 9, 30),
                fiscal_period="Q3",
                form="10-Q",
                frame=None,
            ),
            PeriodBasis.YEAR_TO_DATE,
        ),
        (
            _fact(concept="Assets", start=None, frame="CY2025Q4I"),
            PeriodBasis.INSTANT,
        ),
    ],
)
def test_period_classification(fact: RawXbrlFact, expected: PeriodBasis) -> None:
    assert classify_period(fact).reporting_basis == expected


def test_duration_fact_rejects_instant_frame() -> None:
    with pytest.raises(ValueError, match="instantaneous"):
        classify_period(_fact(frame="CY2025Q4I"))


def test_incompatible_units_are_not_coerced_and_missing_values_are_not_zeroed() -> None:
    result = Normalizer().normalize([_fact(unit="shares")])

    assert result.facts == ()
    categories = [finding.category for finding in result.findings]
    assert categories.count("incompatible_unit") == 1
    assert categories.count("missing_metric") == 31


def test_unmapped_concepts_are_reported_without_guessing() -> None:
    result = Normalizer().normalize([_fact(concept="SalesRevenueNet")])

    assert result.facts == ()
    assert "unmapped_concept" in {finding.category for finding in result.findings}


def test_amendment_selection_is_explicit() -> None:
    original = _fact()
    amendment = _fact(
        fact_id="fact-00000002",
        form="10-K/A",
        filed=date(2026, 3, 1),
        accession="0000000001-26-000002",
    )

    default = Normalizer().normalize([original, amendment])
    amended = Normalizer(policy=SelectionPolicy(prefer_amendments=True)).normalize(
        [original, amendment]
    )

    revenue_default = next(fact for fact in default.facts if fact.canonical_metric == "revenue")
    revenue_amended = next(fact for fact in amended.facts if fact.canonical_metric == "revenue")
    assert revenue_default.accession_number == original.accession_number
    assert revenue_amended.accession_number == amendment.accession_number
    assert "amendment_selected" in {finding.category for finding in amended.findings}


def test_period_filter_excludes_ytd_by_default() -> None:
    annual = _fact()
    ytd = _fact(
        fact_id="fact-00000002",
        start=date(2025, 1, 1),
        end=date(2025, 9, 30),
        fiscal_period="Q3",
        form="10-Q",
        frame=None,
    )
    result = Normalizer().normalize([annual, ytd])

    assert len(select_periods(result.facts, PeriodFilter())) == 1
    selected = select_periods(
        result.facts,
        PeriodFilter(bases=frozenset({PeriodBasis.YEAR_TO_DATE})),
    )
    assert len(selected) == 1
    assert selected[0].period.reporting_basis == PeriodBasis.YEAR_TO_DATE
