from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from filingscope.errors import SecPayloadError
from filingscope.schemas import (
    CompanyIdentity,
    FilingMetadata,
    FinancialPeriod,
    RawFetchManifest,
    RawXbrlFact,
    SourceReference,
)
from filingscope.sec.client import FetchResult, SecHttpClient
from filingscope.sec.identity import normalize_cik
from filingscope.sec.models import CompanyFactsPayload, SubmissionsPayload


class IngestionStore(Protocol):
    def persist_ingestion(
        self,
        company: CompanyIdentity,
        filings: list[FilingMetadata],
        facts: list[RawXbrlFact],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class IngestionResult:
    company: CompanyIdentity
    filings: tuple[FilingMetadata, ...]
    facts: tuple[RawXbrlFact, ...]
    manifests: tuple[RawFetchManifest, ...]
    cache_hits: int


class SecIngestionService:
    def __init__(self, client: SecHttpClient, store: IngestionStore) -> None:
        self.client = client
        self.store = store

    def ingest_company(self, cik: str | int) -> IngestionResult:
        normalized_cik = normalize_cik(cik)
        submissions_url = f"https://data.sec.gov/submissions/CIK{normalized_cik}.json"
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized_cik}.json"
        submissions_raw, submissions_fetch = self.client.fetch_json(
            submissions_url,
            namespace="submissions",
            identity=normalized_cik,
        )
        companyfacts_raw, companyfacts_fetch = self.client.fetch_json(
            facts_url,
            namespace="companyfacts",
            identity=normalized_cik,
        )
        try:
            submissions = SubmissionsPayload.model_validate(submissions_raw)
            companyfacts = CompanyFactsPayload.model_validate(companyfacts_raw)
        except ValidationError as error:
            raise SecPayloadError(
                message="SEC payload failed schema validation; no derived records were emitted",
                code="invalid_sec_payload",
                details={"errors": error.errors(include_url=False)},
            ) from error

        if normalize_cik(submissions.cik) != normalized_cik:
            raise self._identity_mismatch("submissions", normalized_cik, submissions.cik)
        if normalize_cik(companyfacts.cik) != normalized_cik:
            raise self._identity_mismatch("companyfacts", normalized_cik, companyfacts.cik)
        if submissions.name.casefold() != companyfacts.entityName.casefold():
            raise SecPayloadError(
                message="SEC submissions and Company Facts entity names do not match",
                code="sec_entity_mismatch",
                details={"submissions": submissions.name, "companyfacts": companyfacts.entityName},
            )

        company = CompanyIdentity(
            cik=normalized_cik,
            legal_name=submissions.name,
            tickers=tuple(submissions.tickers),
            exchanges=tuple(submissions.exchanges),
            sic=str(submissions.sic) if submissions.sic is not None else None,
        )
        filings = self._filings(normalized_cik, submissions, submissions_fetch)
        facts = self._facts(normalized_cik, companyfacts, companyfacts_fetch)
        self.store.persist_ingestion(company, filings, facts)
        return IngestionResult(
            company=company,
            filings=tuple(filings),
            facts=tuple(facts),
            manifests=(submissions_fetch.manifest, companyfacts_fetch.manifest),
            cache_hits=int(submissions_fetch.from_cache) + int(companyfacts_fetch.from_cache),
        )

    @staticmethod
    def _filings(
        cik: str,
        payload: SubmissionsPayload,
        fetch: FetchResult,
    ) -> list[FilingMetadata]:
        source = _source_reference("sec_submissions", fetch)
        recent = payload.filings.recent
        return [
            FilingMetadata(
                accession_number=accession,
                cik=cik,
                form=form,
                filing_date=recent.filingDate[index],
                report_period=recent.reportDate[index],
                primary_document=recent.primaryDocument[index],
                is_amendment=form.endswith("/A"),
                source=source.model_copy(update={"accession_number": accession}),
            )
            for index, (accession, form) in enumerate(
                zip(recent.accessionNumber, recent.form, strict=True)
            )
        ]

    @staticmethod
    def _facts(
        cik: str,
        payload: CompanyFactsPayload,
        fetch: FetchResult,
    ) -> list[RawXbrlFact]:
        source = _source_reference("sec_companyfacts", fetch)
        facts: list[RawXbrlFact] = []
        for taxonomy, concepts in sorted(payload.facts.items()):
            for concept_name, concept in sorted(concepts.items()):
                for unit, observations in sorted(concept.units.items()):
                    for observation in observations:
                        period = FinancialPeriod(
                            period_type="duration" if observation.start else "instant",
                            start_date=observation.start,
                            end_date=observation.end,
                            fiscal_year=observation.fy,
                            fiscal_period=observation.fp,
                        )
                        fact_id = _fact_id(
                            cik=cik,
                            taxonomy=taxonomy,
                            concept=concept_name,
                            unit=unit,
                            value=observation.val,
                            period=period,
                            accession=observation.accn,
                        )
                        facts.append(
                            RawXbrlFact(
                                fact_id=fact_id,
                                cik=cik,
                                taxonomy=taxonomy,
                                concept=concept_name,
                                label=concept.label,
                                value=observation.val,
                                unit=unit,
                                period=period,
                                form=observation.form,
                                filed=observation.filed,
                                accession_number=observation.accn,
                                frame=observation.frame,
                                decimals=observation.decimals,
                                source=source.model_copy(
                                    update={"accession_number": observation.accn}
                                ),
                            )
                        )
        return sorted(facts, key=lambda fact: fact.fact_id)

    @staticmethod
    def _identity_mismatch(source: str, expected: str, actual: Any) -> SecPayloadError:
        return SecPayloadError(
            message=f"SEC {source} payload CIK does not match requested company",
            code="sec_cik_mismatch",
            details={"expected": expected, "actual": str(actual)},
        )


def _source_reference(
    source_type: Literal["sec_submissions", "sec_companyfacts", "sec_filing"],
    fetch: FetchResult,
) -> SourceReference:
    return SourceReference(
        source_type=source_type,
        source_url=fetch.manifest.canonical_url,
        content_sha256=fetch.manifest.content_sha256,
        manifest_id=fetch.manifest.manifest_id,
        retrieved_at=fetch.manifest.retrieved_at,
    )


def _fact_id(
    *,
    cik: str,
    taxonomy: str,
    concept: str,
    unit: str,
    value: Decimal,
    period: FinancialPeriod,
    accession: str,
) -> str:
    material = "|".join(
        [
            cik,
            taxonomy,
            concept,
            unit,
            str(value),
            period.start_date.isoformat() if period.start_date else "",
            period.end_date.isoformat(),
            accession,
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()
