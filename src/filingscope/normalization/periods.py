from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from filingscope.schemas import FinancialPeriod, NormalizedFinancialFact, PeriodBasis, RawXbrlFact

_ANNUAL_FRAME = re.compile(r"^CY\d{4}$")
_QUARTERLY_FRAME = re.compile(r"^CY\d{4}Q[1-4]$")
_INSTANT_FRAME = re.compile(r"^CY\d{4}(?:Q[1-4])?I$")


def classify_period(fact: RawXbrlFact) -> FinancialPeriod:
    """Classify SEC periods using frame semantics, then documented duration windows."""

    period = fact.period
    if period.period_type == "instant":
        return period.model_copy(update={"reporting_basis": PeriodBasis.INSTANT})

    if fact.frame and _INSTANT_FRAME.fullmatch(fact.frame):
        raise ValueError("duration fact carries an instantaneous SEC frame")
    if fact.frame and _ANNUAL_FRAME.fullmatch(fact.frame):
        basis = PeriodBasis.ANNUAL
    elif fact.frame and _QUARTERLY_FRAME.fullmatch(fact.frame):
        basis = PeriodBasis.QUARTERLY
    else:
        assert period.start_date is not None
        duration_days = (period.end_date - period.start_date).days + 1
        if 335 <= duration_days <= 395:
            basis = PeriodBasis.ANNUAL
        elif 61 <= duration_days <= 121:
            basis = PeriodBasis.QUARTERLY
        elif period.fiscal_period in {"Q2", "Q3"} and 122 <= duration_days <= 304:
            basis = PeriodBasis.YEAR_TO_DATE
        else:
            basis = PeriodBasis.OTHER_DURATION
    return period.model_copy(update={"reporting_basis": basis})


@dataclass(frozen=True, slots=True)
class PeriodFilter:
    bases: frozenset[PeriodBasis] = frozenset(
        {PeriodBasis.INSTANT, PeriodBasis.ANNUAL, PeriodBasis.QUARTERLY}
    )
    start_date: date | None = None
    end_date: date | None = None


def select_periods(
    facts: list[NormalizedFinancialFact] | tuple[NormalizedFinancialFact, ...],
    period_filter: PeriodFilter,
) -> list[NormalizedFinancialFact]:
    selected = [
        fact
        for fact in facts
        if fact.period.reporting_basis in period_filter.bases
        and (period_filter.start_date is None or fact.period.end_date >= period_filter.start_date)
        and (period_filter.end_date is None or fact.period.end_date <= period_filter.end_date)
    ]
    return sorted(
        selected,
        key=lambda fact: (
            fact.canonical_metric,
            fact.period.end_date,
            fact.period.start_date or fact.period.end_date,
            fact.accession_number,
        ),
    )
