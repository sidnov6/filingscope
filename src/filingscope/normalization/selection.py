from __future__ import annotations

from dataclasses import dataclass

from filingscope.schemas import RawXbrlFact


@dataclass(frozen=True, slots=True)
class SelectionPolicy:
    """Explicit controls for duplicate-period and amendment selection."""

    target_accessions: tuple[str, ...] = ()
    prefer_amendments: bool = False


def choose_fact(
    candidates: list[tuple[RawXbrlFact, int]],
    policy: SelectionPolicy,
) -> tuple[RawXbrlFact, int]:
    if not candidates:
        raise ValueError("at least one fact candidate is required")

    target_order = {accession: index for index, accession in enumerate(policy.target_accessions)}

    def ordering(candidate: tuple[RawXbrlFact, int]) -> tuple[int, int, int, int, str]:
        fact, concept_rank = candidate
        target_rank = target_order.get(fact.accession_number, len(target_order))
        amended = fact.form.endswith("/A")
        amendment_rank = int(not amended) if policy.prefer_amendments else int(amended)
        return (
            target_rank,
            concept_rank,
            amendment_rank,
            -fact.filed.toordinal(),
            fact.accession_number,
        )

    return min(candidates, key=ordering)
