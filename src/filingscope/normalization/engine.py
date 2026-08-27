from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from filingscope.normalization.mappings import MappingRegistry
from filingscope.normalization.periods import classify_period
from filingscope.normalization.selection import SelectionPolicy, choose_fact
from filingscope.schemas import (
    DataQualityFinding,
    FindingSeverity,
    NormalizedFinancialFact,
    RawXbrlFact,
)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    facts: tuple[NormalizedFinancialFact, ...]
    findings: tuple[DataQualityFinding, ...]
    mapping_version: str


class Normalizer:
    def __init__(
        self,
        registry: MappingRegistry | None = None,
        policy: SelectionPolicy | None = None,
    ) -> None:
        self.registry = registry or MappingRegistry()
        self.policy = policy or SelectionPolicy()

    def normalize(self, raw_facts: Sequence[RawXbrlFact]) -> NormalizationResult:
        findings: list[DataQualityFinding] = []
        selected: list[NormalizedFinancialFact] = []
        cik = self._single_cik(raw_facts)
        mapped_keys = self.registry.concept_keys()

        for fact in raw_facts:
            if (fact.taxonomy, fact.concept) not in mapped_keys:
                findings.append(
                    self._finding(
                        cik=cik,
                        severity=FindingSeverity.INFO,
                        category="unmapped_concept",
                        metric=None,
                        message=(
                            f"No mapping exists for {fact.taxonomy}:{fact.concept}; "
                            "the fact was not coerced."
                        ),
                        affected=[fact],
                        remediation=(
                            "Review the taxonomy definition before adding a versioned mapping."
                        ),
                    )
                )

        for mapping in self.registry.mappings:
            candidates: list[tuple[RawXbrlFact, int]] = []
            mapping_findings: list[DataQualityFinding] = []
            for concept_rank, concept in enumerate(mapping.concepts, start=1):
                for fact in raw_facts:
                    if (fact.taxonomy, fact.concept) != (concept.taxonomy, concept.concept):
                        continue
                    if fact.unit not in mapping.compatible_units:
                        mapping_findings.append(
                            self._finding(
                                cik=cik,
                                severity=FindingSeverity.ERROR,
                                category="incompatible_unit",
                                metric=mapping.canonical_metric,
                                message=(
                                    f"{fact.taxonomy}:{fact.concept} uses {fact.unit}; expected "
                                    f"one of {', '.join(mapping.compatible_units)}."
                                ),
                                affected=[fact],
                                remediation="Review the source fact unit; do not coerce the value.",
                            )
                        )
                        continue
                    if fact.period.period_type != mapping.period_type:
                        mapping_findings.append(
                            self._finding(
                                cik=cik,
                                severity=FindingSeverity.ERROR,
                                category="incompatible_period_type",
                                metric=mapping.canonical_metric,
                                message=(
                                    f"{fact.taxonomy}:{fact.concept} is {fact.period.period_type}; "
                                    f"the mapping requires {mapping.period_type}."
                                ),
                                affected=[fact],
                                remediation="Review the source context and taxonomy period type.",
                            )
                        )
                        continue
                    if fact.form.removesuffix("/A") not in mapping.allowed_forms:
                        mapping_findings.append(
                            self._finding(
                                cik=cik,
                                severity=FindingSeverity.INFO,
                                category="unsupported_form",
                                metric=mapping.canonical_metric,
                                message=(
                                    f"Form {fact.form} is outside this mapping's allowed forms."
                                ),
                                affected=[fact],
                                remediation=(
                                    "Add an explicit form-selection rule before including it."
                                ),
                            )
                        )
                        continue
                    try:
                        classified = classify_period(fact)
                    except ValueError as error:
                        mapping_findings.append(
                            self._finding(
                                cik=cik,
                                severity=FindingSeverity.ERROR,
                                category="invalid_period_context",
                                metric=mapping.canonical_metric,
                                message=str(error),
                                affected=[fact],
                                remediation="Review the SEC frame and start/end dates.",
                            )
                        )
                        continue
                    candidates.append(
                        (fact.model_copy(update={"period": classified}), concept_rank)
                    )

            findings.extend(mapping_findings)
            if not candidates:
                findings.append(
                    self._finding(
                        cik=cik,
                        severity=FindingSeverity.WARNING,
                        category="missing_metric",
                        metric=mapping.canonical_metric,
                        message=f"No compatible fact was found for {mapping.canonical_metric}.",
                        affected=[],
                        remediation="Review missing concepts, units, forms, and period contexts.",
                    )
                )
                continue

            grouped: dict[tuple[object, ...], list[tuple[RawXbrlFact, int]]] = defaultdict(list)
            for fact, concept_rank in candidates:
                grouped[self._period_key(mapping.canonical_metric, fact)].append(
                    (fact, concept_rank)
                )

            for group in grouped.values():
                chosen, rank = choose_fact(group, self.policy)
                if len(group) > 1:
                    findings.append(
                        self._finding(
                            cik=cik,
                            severity=FindingSeverity.INFO,
                            category="duplicate_period_candidates",
                            metric=mapping.canonical_metric,
                            message=(
                                f"Selected {chosen.accession_number} from {len(group)} facts "
                                "for the same canonical period."
                            ),
                            affected=[fact for fact, _ in group],
                            remediation=(
                                "Inspect retained accessions when amendment provenance matters."
                            ),
                        )
                    )
                if chosen.form.endswith("/A"):
                    findings.append(
                        self._finding(
                            cik=cik,
                            severity=FindingSeverity.WARNING,
                            category="amendment_selected",
                            metric=mapping.canonical_metric,
                            message=f"Selected amended filing fact {chosen.accession_number}.",
                            affected=[chosen],
                            remediation="Compare the amendment with the original filing.",
                        )
                    )
                confidence = mapping.concepts[rank - 1].confidence
                selected.append(
                    NormalizedFinancialFact(
                        normalized_fact_id=self._normalized_id(
                            mapping.canonical_metric, chosen.fact_id
                        ),
                        cik=chosen.cik,
                        canonical_metric=mapping.canonical_metric,
                        original_fact_id=chosen.fact_id,
                        original_taxonomy=chosen.taxonomy,
                        original_concept=chosen.concept,
                        value=chosen.value,
                        unit=chosen.unit,
                        period=chosen.period,
                        form=chosen.form,
                        filed=chosen.filed,
                        accession_number=chosen.accession_number,
                        frame=chosen.frame,
                        decimals=chosen.decimals,
                        mapping_version=self.registry.version,
                        selection_rank=rank,
                        selection_rationale=(
                            f"Selected exact {chosen.taxonomy}:{chosen.concept} mapping at "
                            f"priority {rank}; compatible unit {chosen.unit}; "
                            f"{chosen.period.reporting_basis} period; accession "
                            f"{chosen.accession_number}."
                        ),
                        is_derived=False,
                        is_fallback=rank > 1,
                        data_confidence=confidence,
                        source=chosen.source,
                    )
                )

        if raw_facts:
            findings.append(
                self._finding(
                    cik=cik,
                    severity=FindingSeverity.INFO,
                    category="normalization_summary",
                    metric=None,
                    message=(
                        f"Selected {len(selected)} normalized facts from "
                        f"{len(raw_facts)} raw facts using mapping version "
                        f"{self.registry.version}."
                    ),
                    affected=list(raw_facts),
                    remediation="Review warnings and errors before analytical use.",
                )
            )

        return NormalizationResult(
            facts=tuple(sorted(selected, key=self._normalized_sort_key)),
            findings=tuple(sorted(findings, key=lambda finding: finding.finding_id)),
            mapping_version=self.registry.version,
        )

    @staticmethod
    def _single_cik(raw_facts: Sequence[RawXbrlFact]) -> str | None:
        ciks = {fact.cik for fact in raw_facts}
        if len(ciks) > 1:
            raise ValueError("normalization batch must contain exactly one company")
        return next(iter(ciks), None)

    @staticmethod
    def _period_key(metric: str, fact: RawXbrlFact) -> tuple[object, ...]:
        return (
            metric,
            fact.unit,
            fact.period.start_date,
            fact.period.end_date,
            fact.period.fiscal_year,
            fact.period.fiscal_period,
            fact.period.reporting_basis,
        )

    @staticmethod
    def _normalized_sort_key(fact: NormalizedFinancialFact) -> tuple[object, ...]:
        return (
            fact.canonical_metric,
            fact.period.end_date,
            fact.period.start_date or fact.period.end_date,
            fact.accession_number,
        )

    def _finding(
        self,
        *,
        cik: str | None,
        severity: FindingSeverity,
        category: str,
        metric: str | None,
        message: str,
        affected: list[RawXbrlFact],
        remediation: str,
    ) -> DataQualityFinding:
        affected_ids = tuple(sorted(fact.fact_id for fact in affected))
        finding_id = hashlib.sha256(
            "|".join(
                [self.registry.version, cik or "", category, metric or "", *affected_ids]
            ).encode()
        ).hexdigest()
        unique_sources = {
            source.manifest_id: source for source in (fact.source for fact in affected)
        }
        return DataQualityFinding(
            finding_id=finding_id,
            cik=cik,
            severity=severity,
            category=category,
            metric=metric,
            message=message,
            affected_ids=affected_ids,
            source_references=tuple(unique_sources[key] for key in sorted(unique_sources)),
            mapping_version=self.registry.version,
            remediation=remediation,
        )

    def _normalized_id(self, metric: str, fact_id: str) -> str:
        return hashlib.sha256(f"{self.registry.version}|{metric}|{fact_id}".encode()).hexdigest()
