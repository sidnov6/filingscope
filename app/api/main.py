from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from fastapi.sse import EventSourceResponse, format_sse_event
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from filingscope import __version__
from filingscope.config import Settings
from filingscope.geography import geographic_evidence_from_submissions
from filingscope.investigation.cache import AgentOutputCache
from filingscope.investigation.provider import GroqStructuredProvider
from filingscope.investigation.workflow import InvestigationInputs, InvestigationWorkflow
from filingscope.normalization import (
    MAPPING_VERSION,
    PeriodFilter,
    score_data_quality,
    select_periods,
)
from filingscope.pipeline import DeterministicPipeline
from filingscope.reports import ReportRenderer
from filingscope.schemas import (
    SCHEMA_VERSION,
    CompanyIdentity,
    DataQualityScore,
    EvidencePacket,
    FilingMetadata,
    ForensicTestResult,
    GeographicEvidence,
    InvestigationEvent,
    InvestigationReport,
    NormalizedFinancialFact,
    PeriodBasis,
    Signal,
)
from filingscope.sec.cache import RawResponseCache
from filingscope.sec.client import RateLimiter, SecHttpClient
from filingscope.sec.directory import SecCompanyDirectory
from filingscope.sec.identity import normalize_cik
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


class ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HealthResponse(ApiModel):
    status: str
    product: str
    version: str
    schema_version: str


class ReadinessResponse(ApiModel):
    status: str
    database_available: bool
    companies: int


class VersionResponse(ApiModel):
    application_version: str
    schema_version: str
    mapping_version: str


class ResolveRequest(ApiModel):
    identifier: str = Field(min_length=1)


class IngestionResponse(ApiModel):
    company: CompanyIdentity
    filing_count: int
    raw_fact_count: int
    cache_hits: int
    normalized_fact_count: int
    forensic_test_count: int
    signal_count: int


class CompanySearchItem(ApiModel):
    cik: str
    ticker: str
    legal_name: str
    locally_available: bool


class CompanySearchResponse(ApiModel):
    query: str
    results: tuple[CompanySearchItem, ...]
    official_directory_available: bool
    directory_from_cache: bool = False
    notice: str | None = None


class FinancialsResponse(ApiModel):
    company: CompanyIdentity
    facts: tuple[NormalizedFinancialFact, ...]
    normalized_fact_count: int
    finding_count: int
    missing_metric_count: int
    filings: tuple[FilingMetadata, ...]
    filing_count: int
    available_bases: tuple[PeriodBasis, ...]
    quality_score: DataQualityScore


class CacheStatsResponse(ApiModel):
    manifests: int
    payloads: int


class SignalsResponse(ApiModel):
    company: CompanyIdentity
    metric_count: int
    tests: tuple[ForensicTestResult, ...]
    signals: tuple[Signal, ...]


class EvidenceListResponse(ApiModel):
    company: CompanyIdentity
    evidence: tuple[EvidencePacket, ...]


class GeographyResponse(ApiModel):
    company: CompanyIdentity
    locations: tuple[GeographicEvidence, ...]
    notice: str


class RunSummaryResponse(ApiModel):
    total_runs: int
    complete_runs: int
    partial_runs: int
    deterministic_only_runs: int
    provider_runs: int
    token_usage_available: bool = False


class InvestigationRequest(ApiModel):
    cik: str = Field(min_length=1)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_period(self) -> InvestigationRequest:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not follow end_date")
        if (self.end_date - self.start_date).days > 1_900:
            raise ValueError("investigation period cannot exceed approximately five years")
        return self


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings()
    store = ParquetDuckDbStore(active_settings.data_dir)
    application = FastAPI(
        title="FilingScope API",
        version=__version__,
        description="Deterministic SEC financial-intelligence research API.",
    )

    @application.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            product="filingscope",
            version=__version__,
            schema_version=SCHEMA_VERSION,
        )

    @application.get("/ready", response_model=ReadinessResponse, tags=["operations"])
    def readiness() -> ReadinessResponse:
        companies = store.companies()
        return ReadinessResponse(
            status="ready",
            database_available=store.database_path.exists(),
            companies=len(companies),
        )

    @application.get("/version", response_model=VersionResponse, tags=["operations"])
    def version() -> VersionResponse:
        return VersionResponse(
            application_version=__version__,
            schema_version=SCHEMA_VERSION,
            mapping_version=MAPPING_VERSION,
        )

    @application.get("/cache/stats", response_model=CacheStatsResponse, tags=["operations"])
    def cache_stats() -> CacheStatsResponse:
        raw_dir = active_settings.data_dir / "raw" / "sec"
        return CacheStatsResponse(
            manifests=_file_count(raw_dir / "manifests", "*.json"),
            payloads=_file_count(raw_dir / "payloads", "*.bin"),
        )

    @application.get("/runs/summary", response_model=RunSummaryResponse, tags=["operations"])
    def run_summary() -> RunSummaryResponse:
        runs = store.investigation_runs()
        return RunSummaryResponse(
            total_runs=len(runs),
            complete_runs=sum(run.status == "complete" for run in runs),
            partial_runs=sum(run.status == "partial" for run in runs),
            deterministic_only_runs=sum(run.deterministic_only for run in runs),
            provider_runs=sum(not run.deterministic_only for run in runs),
        )

    @application.post("/companies/resolve", response_model=CompanyIdentity, tags=["companies"])
    def resolve_company(request: ResolveRequest) -> CompanyIdentity:
        identifier = request.identifier.strip()
        companies = store.companies()
        if identifier.isdigit():
            normalized = normalize_cik(identifier)
            company = next((row for row in companies if row.cik == normalized), None)
        else:
            folded = identifier.casefold()
            matches = [
                row
                for row in companies
                if folded == row.legal_name.casefold()
                or any(folded == ticker.casefold() for ticker in row.tickers)
            ]
            company = matches[0] if len(matches) == 1 else None
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not uniquely resolved locally")
        return company

    @application.get(
        "/companies/search",
        response_model=CompanySearchResponse,
        tags=["companies"],
    )
    def search_companies(
        q: Annotated[str, Query(min_length=1, max_length=120)],
        limit: Annotated[int, Query(ge=1, le=25)] = 12,
    ) -> CompanySearchResponse:
        query = q.strip()
        local = store.companies()
        folded = query.casefold()
        local_items = [
            CompanySearchItem(
                cik=company.cik,
                ticker=company.tickers[0] if company.tickers else "—",
                legal_name=company.legal_name,
                locally_available=True,
            )
            for company in local
            if folded in company.legal_name.casefold()
            or any(folded in ticker.casefold() for ticker in company.tickers)
            or (query.isdigit() and normalize_cik(query) == company.cik)
        ]
        if active_settings.sec_user_agent is None:
            return CompanySearchResponse(
                query=query,
                results=tuple(local_items[:limit]),
                official_directory_available=False,
                notice=(
                    "Live SEC directory search is disabled until an identifiable SEC User-Agent "
                    "is configured. Locally prepared companies remain searchable."
                ),
            )
        with httpx.Client() as http_client:
            client = SecHttpClient(
                user_agent=active_settings.require_sec_user_agent(),
                cache=RawResponseCache(active_settings.data_dir),
                http_client=http_client,
                rate_limiter=RateLimiter(active_settings.sec_min_interval_seconds),
                timeout_seconds=active_settings.sec_timeout_seconds,
                cache_max_age_seconds=active_settings.sec_cache_max_age_seconds,
                max_response_bytes=active_settings.sec_max_response_bytes,
            )
            directory = SecCompanyDirectory(client).search(query, limit=limit)
        local_ciks = {company.cik for company in local}
        results = tuple(
            CompanySearchItem(
                cik=entry.cik,
                ticker=entry.ticker,
                legal_name=entry.legal_name,
                locally_available=entry.cik in local_ciks,
            )
            for entry in directory.entries
        )
        return CompanySearchResponse(
            query=query,
            results=results,
            official_directory_available=True,
            directory_from_cache=directory.from_cache,
        )

    @application.post("/ingestion/{cik}", response_model=IngestionResponse, tags=["ingestion"])
    def ingest_company(cik: str) -> IngestionResponse:
        try:
            user_agent = active_settings.require_sec_user_agent()
        except ValueError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        with httpx.Client() as http_client:
            client = SecHttpClient(
                user_agent=user_agent,
                cache=RawResponseCache(active_settings.data_dir),
                http_client=http_client,
                rate_limiter=RateLimiter(active_settings.sec_min_interval_seconds),
                timeout_seconds=active_settings.sec_timeout_seconds,
                cache_max_age_seconds=active_settings.sec_cache_max_age_seconds,
                max_response_bytes=active_settings.sec_max_response_bytes,
            )
            result = SecIngestionService(client, store).ingest_company(cik)
        analysis = DeterministicPipeline(store).run(result.company.cik, result.facts)
        return IngestionResponse(
            company=result.company,
            filing_count=len(result.filings),
            raw_fact_count=len(result.facts),
            cache_hits=result.cache_hits,
            normalized_fact_count=len(analysis.normalized_facts),
            forensic_test_count=len(analysis.tests),
            signal_count=len(analysis.signals),
        )

    @application.get(
        "/companies/{cik}/financials",
        response_model=FinancialsResponse,
        tags=["companies"],
    )
    def company_financials(
        cik: str,
        basis: Annotated[list[PeriodBasis] | None, Query()] = None,
        start_date: date | None = None,
        end_date: date | None = None,
        periods_per_metric: Annotated[int, Query(ge=1, le=40)] = 12,
    ) -> FinancialsResponse:
        normalized = normalize_cik(cik)
        company = store.company(normalized)
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not available locally")
        facts = store.normalized_facts(normalized)
        findings = store.data_quality_findings(normalized)
        filings = store.filings(normalized)
        requested_bases = frozenset(basis) if basis else PeriodFilter().bases
        selected = select_periods(
            facts,
            PeriodFilter(bases=requested_bases, start_date=start_date, end_date=end_date),
        )
        recent_by_metric: dict[str, list[NormalizedFinancialFact]] = {}
        for fact in selected:
            recent_by_metric.setdefault(fact.canonical_metric, []).append(fact)
        selected = [
            fact
            for metric in sorted(recent_by_metric)
            for fact in recent_by_metric[metric][-periods_per_metric:]
        ]
        return FinancialsResponse(
            company=company,
            facts=tuple(selected),
            normalized_fact_count=len(facts),
            finding_count=len(findings),
            missing_metric_count=sum(finding.category == "missing_metric" for finding in findings),
            filings=tuple(filings[:50]),
            filing_count=len(filings),
            available_bases=tuple(
                sorted(
                    {
                        fact.period.reporting_basis
                        for fact in facts
                        if fact.period.reporting_basis is not None
                    },
                    key=str,
                )
            ),
            quality_score=score_data_quality(
                normalized,
                facts,
                findings,
            ),
        )

    @application.get(
        "/companies/{cik}/signals",
        response_model=SignalsResponse,
        tags=["companies"],
    )
    def company_signals(cik: str) -> SignalsResponse:
        normalized = normalize_cik(cik)
        company = store.company(normalized)
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not available locally")
        metrics = store.metric_results(normalized)
        return SignalsResponse(
            company=company,
            metric_count=len(metrics),
            tests=tuple(store.test_results(normalized)),
            signals=tuple(store.signals(normalized)),
        )

    @application.get(
        "/companies/{cik}/evidence",
        response_model=EvidenceListResponse,
        tags=["evidence"],
    )
    def company_evidence(cik: str) -> EvidenceListResponse:
        normalized = normalize_cik(cik)
        company = store.company(normalized)
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not available locally")
        return EvidenceListResponse(
            company=company,
            evidence=tuple(store.evidence_packets(normalized)),
        )

    @application.get(
        "/companies/{cik}/geography",
        response_model=GeographyResponse,
        tags=["companies"],
    )
    def company_geography(cik: str) -> GeographyResponse:
        normalized = normalize_cik(cik)
        company = store.company(normalized)
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not available locally")
        url = f"https://data.sec.gov/submissions/CIK{normalized}.json"
        cached = RawResponseCache(active_settings.data_dir).lookup(url)
        locations: tuple[GeographicEvidence, ...] = ()
        if cached is not None:
            try:
                payload = json.loads(cached.payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            locations = geographic_evidence_from_submissions(
                payload,
                source_url=url,
                source_hash=cached.manifest.content_sha256,
            )
        return GeographyResponse(
            company=company,
            locations=locations,
            notice=(
                "Only SEC-sourced registered-address context is shown. Markers do not represent "
                "revenue, assets, suppliers, customers, or operating exposure."
            ),
        )

    @application.post(
        "/investigations",
        response_model=InvestigationReport,
        tags=["investigations"],
    )
    def create_investigation(request: InvestigationRequest) -> InvestigationReport:
        report = run_investigation(request)
        persist_report(report)
        return report

    def build_inputs(request: InvestigationRequest) -> InvestigationInputs:
        normalized = normalize_cik(request.cik)
        company = store.company(normalized)
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not available locally")
        facts = tuple(
            fact
            for fact in store.normalized_facts(normalized)
            if request.start_date <= fact.period.end_date <= request.end_date
        )
        metrics = tuple(
            metric
            for metric in store.metric_results(normalized)
            if request.start_date <= metric.period.end_date <= request.end_date
        )
        tests = tuple(
            result
            for result in store.test_results(normalized)
            if request.start_date <= result.period.end_date <= request.end_date
        )
        anomalies = tuple(
            anomaly
            for anomaly in store.anomalies(normalized)
            if request.start_date <= anomaly.period.end_date <= request.end_date
        )
        inputs = InvestigationInputs(
            company=company,
            requested_period_start=request.start_date,
            requested_period_end=request.end_date,
            findings=tuple(store.data_quality_findings(normalized)),
            normalized_facts=facts,
            metrics=metrics,
            tests=tests,
            anomalies=anomalies,
            signals=tuple(store.signals(normalized)),
            evidence=tuple(store.evidence_packets(normalized)),
            mapping_version=facts[0].mapping_version if facts else MAPPING_VERSION,
        )
        return inputs

    def run_investigation(
        request: InvestigationRequest,
        on_event: Callable[[InvestigationEvent], None] | None = None,
    ) -> InvestigationReport:
        inputs = build_inputs(request)
        cache = AgentOutputCache(active_settings.data_dir / "agent-cache")
        if active_settings.groq_api_key and active_settings.groq_reasoning_model:
            with httpx.Client() as provider_client:
                provider = GroqStructuredProvider(
                    api_key=active_settings.groq_api_key.get_secret_value(),
                    model_name=active_settings.groq_reasoning_model,
                    base_url=active_settings.groq_base_url,
                    http_client=provider_client,
                    max_retries=active_settings.investigation_max_retries,
                )
                report = InvestigationWorkflow(
                    provider=provider,
                    cache=cache,
                    max_signals=active_settings.investigation_max_signals,
                    max_evidence_packets=active_settings.investigation_max_evidence_packets,
                    wall_clock_seconds=active_settings.investigation_wall_clock_seconds,
                    on_event=on_event,
                ).run(inputs)
        else:
            report = InvestigationWorkflow(
                cache=cache,
                max_signals=active_settings.investigation_max_signals,
                max_evidence_packets=active_settings.investigation_max_evidence_packets,
                wall_clock_seconds=active_settings.investigation_wall_clock_seconds,
                on_event=on_event,
            ).run(inputs)

        return report

    def persist_report(report: InvestigationReport) -> None:
        store.persist_investigation_run(report.run)
        store.persist_agent_outputs(report)
        ReportRenderer().write(report, active_settings.data_dir / "reports")

    @application.get(
        "/investigations/stream",
        response_model=None,
        tags=["investigations"],
    )
    async def stream_investigation(
        cik: str,
        start_date: date,
        end_date: date,
    ) -> EventSourceResponse:
        try:
            request = InvestigationRequest(cik=cik, start_date=start_date, end_date=end_date)
        except ValidationError as error:
            raise HTTPException(
                status_code=422,
                detail=error.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                ),
            ) from error
        build_inputs(request)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[InvestigationEvent | Exception | None] = asyncio.Queue()

        def publish(event: InvestigationEvent) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def worker() -> None:
            try:
                report = run_investigation(request, publish)
                persist_report(report)
            except Exception as error:  # the stream reports a safe terminal state
                loop.call_soon_threadsafe(queue.put_nowait, error)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        async def event_stream() -> AsyncIterator[bytes]:
            task = asyncio.create_task(asyncio.to_thread(worker))
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    yield format_sse_event(
                        data_str=json.dumps(
                            {
                                "sequence": 1,
                                "run_id": "unavailable",
                                "role": "system",
                                "status": "failed",
                                "title": "Investigation failed safely",
                                "message": "The run stopped before a valid report was produced.",
                                "emitted_at": "unavailable",
                            },
                            separators=(",", ":"),
                        )
                    )
                    continue
                yield format_sse_event(data_str=item.model_dump_json())
            await task

        return EventSourceResponse(event_stream())

    @application.get(
        "/investigations/{run_id}",
        response_model=InvestigationReport,
        tags=["investigations"],
    )
    def get_investigation(run_id: str) -> InvestigationReport:
        return _load_report(active_settings.data_dir, run_id)

    @application.get("/evidence/{evidence_id}", response_model=EvidencePacket, tags=["evidence"])
    def get_evidence(evidence_id: str) -> EvidencePacket:
        packet = store.evidence_packet(evidence_id)
        if packet is None:
            raise HTTPException(status_code=404, detail="Evidence packet is not available")
        return packet

    @application.get("/reports/{run_id}", tags=["reports"], response_model=None)
    def get_report(
        run_id: str,
        format: Literal["json", "markdown"] = "json",
    ) -> InvestigationReport | PlainTextResponse:
        report = _load_report(active_settings.data_dir, run_id)
        if format == "markdown":
            return PlainTextResponse(
                ReportRenderer().render_markdown(report),
                media_type="text/markdown",
            )
        return report

    return application


def _file_count(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def _load_report(data_dir: Path, run_id: str) -> InvestigationReport:
    if len(run_id) != 64 or any(character not in "0123456789abcdef" for character in run_id):
        raise HTTPException(status_code=404, detail="Investigation report is not available")
    path = data_dir / "reports" / run_id / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Investigation report is not available")
    return ReportRenderer.read(path)


app = create_app()
