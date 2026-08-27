from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from filingscope.normalization.mappings import MappingRegistry
from filingscope.schemas import (
    DataQualityFinding,
    DataQualityScore,
    NormalizedFinancialFact,
    PeriodBasis,
)


def score_data_quality(
    cik: str,
    facts: Sequence[NormalizedFinancialFact],
    findings: Sequence[DataQualityFinding],
    registry: MappingRegistry | None = None,
) -> DataQualityScore:
    active_registry = registry or MappingRegistry()
    mapped_metrics = {fact.canonical_metric for fact in facts}
    completeness = Decimal(len(mapped_metrics)) / Decimal(len(active_registry.mappings))
    incompatible_units = sum(finding.category == "incompatible_unit" for finding in findings)
    unit_consistency = Decimal("1") if not incompatible_units else Decimal("0")
    confidences = [fact.data_confidence for fact in facts]
    mapping_confidence = (
        sum(confidences, Decimal("0")) / Decimal(len(confidences)) if confidences else Decimal("0")
    )
    aligned = sum(
        fact.period.reporting_basis not in {None, PeriodBasis.OTHER_DURATION} for fact in facts
    )
    period_alignment = Decimal(aligned) / Decimal(len(facts)) if facts else Decimal("0")
    amendment_status = (
        Decimal("0")
        if any(finding.category == "amendment_selected" for finding in findings)
        else Decimal("1")
    )
    components = [
        completeness,
        unit_consistency,
        mapping_confidence,
        period_alignment,
        amendment_status,
    ]
    overall = sum(components, Decimal("0")) / Decimal(len(components))
    mapping_version = facts[0].mapping_version if facts else active_registry.version
    return DataQualityScore(
        cik=cik,
        mapping_version=mapping_version,
        completeness=completeness,
        unit_consistency=unit_consistency,
        mapping_confidence=mapping_confidence,
        period_alignment=period_alignment,
        amendment_status=amendment_status,
        reconciliation=None,
        overall=overall,
        explanation=(
            "Unweighted mean of available completeness, unit consistency, mapping confidence, "
            "period alignment, and amendment-status components. Reconciliation is unavailable "
            "until statement coverage supports it."
        ),
    )
