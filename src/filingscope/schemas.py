from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

SCHEMA_VERSION = "1.0.0"
_CIK_PATTERN = re.compile(r"^\d{10}$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SignalSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ComputationStatus(StrEnum):
    COMPUTED = "computed"
    NOT_COMPUTABLE = "not_computable"


class VerificationStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class PeriodBasis(StrEnum):
    INSTANT = "instant"
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    YEAR_TO_DATE = "year_to_date"
    OTHER_DURATION = "other_duration"


class InvestigationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    PARTIAL = "partial"


class InvestigationEvent(FrozenModel):
    sequence: int = Field(ge=1)
    run_id: str = Field(min_length=12)
    role: Literal["system", "planner", "investigator", "bull", "skeptical", "verifier", "judge"]
    status: Literal["queued", "running", "complete", "skipped", "failed"]
    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    output: dict[str, Any] | None = None
    emitted_at: datetime


class CompanyIdentity(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    legal_name: str = Field(min_length=1)
    tickers: tuple[str, ...] = ()
    exchanges: tuple[str, ...] = ()
    sic: str | None = None

    @model_validator(mode="after")
    def normalize_identity(self) -> CompanyIdentity:
        tickers = tuple(sorted({ticker.upper() for ticker in self.tickers}))
        exchanges = tuple(sorted(set(self.exchanges)))
        object.__setattr__(self, "tickers", tickers)
        object.__setattr__(self, "exchanges", exchanges)
        return self


class SourceReference(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    source_type: Literal["sec_submissions", "sec_companyfacts", "sec_filing"]
    source_url: HttpUrl
    content_sha256: str = Field(pattern=_SHA256_PATTERN.pattern)
    manifest_id: str = Field(min_length=12)
    retrieved_at: datetime
    accession_number: str | None = None


class FilingMetadata(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    accession_number: str = Field(min_length=1)
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    form: str = Field(min_length=1)
    filing_date: date
    report_period: date | None = None
    primary_document: str = Field(min_length=1)
    is_amendment: bool = False
    source: SourceReference


class RawFetchManifest(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    manifest_id: str = Field(min_length=12)
    canonical_url: HttpUrl
    retrieved_at: datetime
    http_status: int = Field(ge=100, le=599)
    content_type: str | None = None
    byte_length: int = Field(ge=0)
    etag: str | None = None
    last_modified: str | None = None
    content_sha256: str = Field(pattern=_SHA256_PATTERN.pattern)
    relative_path: str = Field(min_length=1)
    accession_number: str | None = None
    attempt_count: int = Field(default=1, ge=1)


class FinancialPeriod(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    period_type: Literal["instant", "duration"]
    start_date: date | None = None
    end_date: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    reporting_basis: PeriodBasis | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> FinancialPeriod:
        if self.period_type == "duration" and self.start_date is None:
            raise ValueError("duration periods require start_date")
        if self.period_type == "instant" and self.start_date is not None:
            raise ValueError("instant periods must not include start_date")
        if self.start_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date must not follow end_date")
        if self.period_type == "instant" and self.reporting_basis not in {
            None,
            PeriodBasis.INSTANT,
        }:
            raise ValueError("instant periods cannot use a duration reporting basis")
        if self.period_type == "duration" and self.reporting_basis == PeriodBasis.INSTANT:
            raise ValueError("duration periods cannot use the instant reporting basis")
        return self


class RawXbrlFact(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    fact_id: str = Field(min_length=12)
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    taxonomy: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    label: str | None = None
    value: Decimal
    unit: str = Field(min_length=1)
    period: FinancialPeriod
    form: str = Field(min_length=1)
    filed: date
    accession_number: str = Field(min_length=1)
    frame: str | None = None
    decimals: int | None = None
    source: SourceReference


class NormalizedFinancialFact(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    normalized_fact_id: str = Field(min_length=12)
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    canonical_metric: str = Field(min_length=1)
    original_fact_id: str = Field(min_length=12)
    original_taxonomy: str = Field(min_length=1)
    original_concept: str = Field(min_length=1)
    value: Decimal
    unit: str = Field(min_length=1)
    period: FinancialPeriod
    form: str = Field(min_length=1)
    filed: date
    accession_number: str = Field(min_length=1)
    frame: str | None = None
    decimals: int | None = None
    mapping_version: str = Field(min_length=1)
    selection_rank: int = Field(ge=1)
    selection_rationale: str = Field(min_length=1)
    is_derived: bool = False
    is_fallback: bool = False
    data_confidence: Decimal = Field(ge=0, le=1)
    source: SourceReference

    @model_validator(mode="after")
    def require_classified_period(self) -> NormalizedFinancialFact:
        if self.period.reporting_basis is None:
            raise ValueError("normalized facts require a classified reporting basis")
        return self


class DataQualityFinding(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    finding_id: str = Field(min_length=12)
    cik: str | None = Field(default=None, pattern=_CIK_PATTERN.pattern)
    severity: FindingSeverity
    category: str = Field(min_length=1)
    metric: str | None = None
    message: str = Field(min_length=1)
    affected_ids: tuple[str, ...] = ()
    source_references: tuple[SourceReference, ...] = ()
    mapping_version: str | None = None
    remediation: str | None = None


class DataQualityScore(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    mapping_version: str = Field(min_length=1)
    completeness: Decimal = Field(ge=0, le=1)
    unit_consistency: Decimal = Field(ge=0, le=1)
    mapping_confidence: Decimal = Field(ge=0, le=1)
    period_alignment: Decimal = Field(ge=0, le=1)
    amendment_status: Decimal = Field(ge=0, le=1)
    reconciliation: Decimal | None = Field(default=None, ge=0, le=1)
    overall: Decimal = Field(ge=0, le=1)
    explanation: str = Field(min_length=1)


class MetricResult(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    metric_result_id: str = Field(min_length=12)
    metric_id: str = Field(min_length=1)
    formula_version: str = Field(min_length=1)
    period: FinancialPeriod
    status: ComputationStatus
    value: Decimal | None = None
    unit: str | None = None
    input_fact_ids: tuple[str, ...] = ()
    comparability_flags: tuple[str, ...] = ()
    data_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    not_computable_reason: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> MetricResult:
        if self.status == ComputationStatus.COMPUTED and self.value is None:
            raise ValueError("computed metric must have a value")
        if self.status == ComputationStatus.NOT_COMPUTABLE and not self.not_computable_reason:
            raise ValueError("not-computable metric must include a reason")
        return self


class ForensicTestResult(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    test_result_id: str = Field(min_length=12)
    test_id: str = Field(min_length=1)
    test_version: str = Field(min_length=1)
    period: FinancialPeriod
    status: ComputationStatus
    result: Decimal | str | None = None
    threshold_context: dict[str, Any] = Field(default_factory=dict)
    metric_result_ids: tuple[str, ...] = ()
    data_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)


class Signal(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    signal_id: str = Field(min_length=12)
    category: str = Field(min_length=1)
    test_id: str = Field(min_length=1)
    severity: SignalSeverity
    materiality: Decimal | None = None
    persistence: Literal["one_off", "recurring", "worsening", "unknown"]
    data_confidence: Decimal = Field(ge=0, le=1)
    evidence_requirements: tuple[str, ...]
    score: Decimal
    score_explanation: str = Field(min_length=1)
    source_test_result_ids: tuple[str, ...]


class EvidencePacket(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    evidence_id: str = Field(min_length=1)
    signal_id: str = Field(min_length=12)
    source: SourceReference
    section: str = Field(min_length=1)
    subsection: str | None = None
    chunk_id: str = Field(min_length=12)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    excerpt: str = Field(min_length=1)
    relevance_score: Decimal = Field(ge=0)
    selection_reason: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    token_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> EvidencePacket:
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must follow start_offset")
        return self


class GeographicEvidence(FrozenModel):
    geographic_evidence_id: str = Field(min_length=12)
    label: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precision: Literal["administrative_area_centroid"]
    context: Literal["registered_business_address"]
    address: str = Field(min_length=1)
    source_url: HttpUrl
    source_sha256: str = Field(pattern=_SHA256_PATTERN.pattern)
    limitation: str = Field(min_length=1)


class FilingChunk(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    chunk_id: str = Field(min_length=12)
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    ticker: str | None = None
    accession_number: str = Field(min_length=1)
    form: str = Field(min_length=1)
    filing_date: date
    report_period: date | None = None
    section: str = Field(min_length=1)
    subsection: str | None = None
    sequence: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    source_url: HttpUrl
    parser_version: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN.pattern)
    source: SourceReference

    @model_validator(mode="after")
    def validate_chunk_offsets(self) -> FilingChunk:
        if self.end_offset <= self.start_offset:
            raise ValueError("chunk end_offset must follow start_offset")
        return self


class AnomalyResult(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    anomaly_id: str = Field(min_length=12)
    metric_id: str = Field(min_length=1)
    period: FinancialPeriod
    current_value: Decimal
    year_over_year_change: Decimal | None = None
    quarter_over_quarter_change: Decimal | None = None
    historical_median: Decimal | None = None
    median_absolute_deviation: Decimal | None = None
    robust_z_score: Decimal | None = None
    rolling_percentile: Decimal | None = Field(default=None, ge=0, le=1)
    sample_count: int = Field(ge=1)
    persistence: Literal["one_off", "recurring", "worsening", "unknown"]
    input_metric_result_ids: tuple[str, ...]
    explanation: str = Field(min_length=1)


class PeerContext(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    metric_id: str = Field(min_length=1)
    period: FinancialPeriod
    status: ComputationStatus
    company_value: Decimal | None = None
    peer_median: Decimal | None = None
    peer_first_quartile: Decimal | None = None
    peer_third_quartile: Decimal | None = None
    percentile: Decimal | None = Field(default=None, ge=0, le=1)
    peer_count: int = Field(ge=0)
    peer_ciks: tuple[str, ...] = ()
    reason: str = Field(min_length=1)


class InvestigationPlan(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    plan_id: str = Field(min_length=12)
    signal_ids: tuple[str, ...]
    questions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    stop_conditions: tuple[str, ...]


class InvestigationClaim(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    claim_id: str = Field(min_length=12)
    role: Literal["investigator", "bull", "skeptical"]
    text: str = Field(min_length=1)
    signal_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    fact_ids: tuple[str, ...] = ()
    metric_result_ids: tuple[str, ...] = ()
    confidence: Decimal = Field(ge=0, le=1)
    material: bool = True

    @model_validator(mode="after")
    def require_claim_support_reference(self) -> InvestigationClaim:
        if self.material and not (self.evidence_ids or self.fact_ids or self.metric_result_ids):
            raise ValueError("material claims require evidence, fact, or metric references")
        return self


class AgentCase(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    role: Literal["investigator", "bull", "skeptical"]
    claims: tuple[InvestigationClaim, ...]
    evidence_gaps: tuple[str, ...] = ()
    falsifiers: tuple[str, ...] = ()


class ClaimVerification(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    claim_id: str = Field(min_length=12)
    status: VerificationStatus
    checked_evidence_ids: tuple[str, ...] = ()
    explanation: str = Field(min_length=1)


class VerificationBatch(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    verifications: tuple[ClaimVerification, ...]


class FinalAssessment(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    assessment_id: str = Field(min_length=12)
    summary: str = Field(min_length=1)
    strongest_concern: str | None = None
    alternative_explanations: tuple[str, ...] = ()
    verified_claim_ids: tuple[str, ...] = ()
    unresolved_claim_ids: tuple[str, ...] = ()
    confidence: Decimal = Field(ge=0, le=1)
    limitations: tuple[str, ...]
    risk_language_disclosure: str = Field(min_length=1)

    @model_validator(mode="after")
    def reject_accusatory_language(self) -> FinalAssessment:
        combined = " ".join(
            filter(
                None,
                [self.summary, self.strongest_concern or "", *self.alternative_explanations],
            )
        ).casefold()
        banned = ("committed fraud", "is fraudulent", "proves fraud", "fraud was committed")
        if any(phrase in combined for phrase in banned):
            raise ValueError("assessment must use screening-risk language, not accusations")
        return self


class InvestigationReport(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    run: InvestigationRunMetadata
    company: CompanyIdentity
    findings: tuple[DataQualityFinding, ...]
    metrics: tuple[MetricResult, ...]
    tests: tuple[ForensicTestResult, ...]
    anomalies: tuple[AnomalyResult, ...]
    signals: tuple[Signal, ...]
    evidence: tuple[EvidencePacket, ...]
    plan: InvestigationPlan | None = None
    investigator: AgentCase | None = None
    bull_case: AgentCase | None = None
    skeptical_case: AgentCase | None = None
    verifications: tuple[ClaimVerification, ...] = ()
    assessment: FinalAssessment | None = None
    deterministic_only: bool = True


class AgentOutputRecord(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    output_id: str = Field(min_length=12)
    run_id: str = Field(min_length=12)
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    role: Literal["planner", "investigator", "bull", "skeptical", "verifier", "judge"]
    prompt_version: str
    model_name: str
    validated: bool = True
    output_json: str = Field(min_length=2)


class InvestigationRunMetadata(FrozenModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(min_length=12)
    cik: str = Field(pattern=_CIK_PATTERN.pattern)
    requested_period_start: date
    requested_period_end: date
    status: InvestigationStatus
    deterministic_only: bool = True
    configuration_hash: str = Field(pattern=_SHA256_PATTERN.pattern)
    source_manifest_ids: tuple[str, ...]
    mapping_version: str | None = None
    prompt_version: str | None = None
    model_metadata: dict[str, str] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None
    stop_reason: str | None = None

    @model_validator(mode="after")
    def validate_run(self) -> InvestigationRunMetadata:
        if self.requested_period_start > self.requested_period_end:
            raise ValueError("requested period start must not follow end")
        return self
