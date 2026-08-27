from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from filingscope.config import Settings
from filingscope.filings import FilingDocumentParser
from filingscope.investigation.workflow import InvestigationInputs, InvestigationWorkflow
from filingscope.pipeline import DeterministicPipeline
from filingscope.reports import ReportRenderer
from filingscope.retrieval import EvidenceBuilder, FilingSearchIndex
from filingscope.schemas import FilingMetadata, Signal, SignalSeverity, SourceReference
from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


@pytest.mark.integration
def test_raw_fixture_to_api_and_deterministic_report(
    tmp_path: Path,
    fixture_dir: Path,
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    submissions = (fixture_dir / "aapl_submissions_excerpt.json").read_bytes()
    companyfacts = (fixture_dir / "aapl_companyfacts_excerpt.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        content = companyfacts if "companyfacts" in request.url.path else submissions
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    store = ParquetDuckDbStore(tmp_path)
    ingestion = SecIngestionService(
        client_factory(httpx.MockTransport(handler)), store
    ).ingest_company("320193")
    analysis = DeterministicPipeline(store).run(ingestion.company.cik, ingestion.facts)

    assert len(analysis.normalized_facts) == 6
    assert len(analysis.tests) == 32
    assert analysis.signals == ()
    assert len(store.metric_results(ingestion.company.cik)) == len(analysis.metrics)
    assert len(store.test_results(ingestion.company.cik)) == 32

    payload = (fixture_dir / "aapl_2018_10k_excerpt.html").read_bytes()
    source = SourceReference(
        source_type="sec_filing",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019318000145/a10-k20189292018.htm"
        ),
        content_sha256=hashlib.sha256(payload).hexdigest(),
        manifest_id="manifest-e2e-filing",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
        accession_number="0000320193-18-000145",
    )
    filing = FilingMetadata(
        accession_number="0000320193-18-000145",
        cik=ingestion.company.cik,
        form="10-K",
        filing_date=date(2018, 11, 5),
        report_period=date(2018, 9, 29),
        primary_document="a10-k20189292018.htm",
        source=source,
    )
    chunks = FilingDocumentParser().parse(payload, filing, source, ticker="AAPL")
    store.persist_filing_chunks(cik=ingestion.company.cik, chunks=list(chunks))
    index = FilingSearchIndex(tmp_path / "filing-search.sqlite3")
    index.index(chunks)
    retrieval_signal = Signal(
        signal_id="signal-e2e-retrieval",
        category="controls",
        test_id="internal_control_review",
        severity=SignalSeverity.MODERATE,
        persistence="unknown",
        data_confidence=Decimal("1"),
        evidence_requirements=("Item 9A internal control effective",),
        score=Decimal("0.5"),
        score_explanation="Retrieval-only fixture label; not an analytical conclusion.",
        source_test_result_ids=("test-e2e-retrieval",),
    )
    packets = EvidenceBuilder(index).for_signals(ingestion.company.cik, [retrieval_signal])
    store.persist_evidence(cik=ingestion.company.cik, packets=list(packets))
    assert packets and packets[0].section == "Item 9A"

    report = InvestigationWorkflow(now=lambda: datetime(2026, 8, 27, 12, 0, tzinfo=UTC)).run(
        InvestigationInputs(
            company=ingestion.company,
            requested_period_start=date(2021, 7, 1),
            requested_period_end=date(2026, 6, 27),
            findings=analysis.findings,
            normalized_facts=analysis.normalized_facts,
            metrics=analysis.metrics,
            tests=analysis.tests,
            anomalies=analysis.anomalies,
            signals=analysis.signals,
            evidence=(),
            mapping_version=analysis.mapping_version,
        )
    )
    paths = ReportRenderer().write(report, tmp_path / "reports")
    assert ReportRenderer.read(paths["json"]) == report
    assert report.deterministic_only

    api = TestClient(create_app(Settings(environment="test", data_dir=tmp_path)))
    assert api.post("/companies/resolve", json={"identifier": "AAPL"}).status_code == 200
    financials = api.get(f"/companies/{ingestion.company.cik}/financials")
    assert financials.status_code == 200
    assert len(financials.json()["facts"]) == 5
    signals = api.get(f"/companies/{ingestion.company.cik}/signals")
    assert signals.status_code == 200
    assert signals.json()["metric_count"] == 10
    assert len(signals.json()["tests"]) == 32
    evidence = api.get(f"/evidence/{packets[0].evidence_id}")
    assert evidence.status_code == 200

    created = api.post(
        "/investigations",
        json={
            "cik": ingestion.company.cik,
            "start_date": "2021-07-01",
            "end_date": "2026-06-27",
        },
    )
    assert created.status_code == 200
    run_id = created.json()["run"]["run_id"]
    assert api.get(f"/investigations/{run_id}").status_code == 200
    markdown = api.get(f"/reports/{run_id}?format=markdown")
    assert markdown.status_code == 200
    assert "does not establish fraud" in markdown.text
    summary = api.get("/runs/summary")
    assert summary.status_code == 200
    assert summary.json() == {
        "total_runs": 1,
        "complete_runs": 1,
        "partial_runs": 0,
        "deterministic_only_runs": 1,
        "provider_runs": 0,
        "token_usage_available": False,
    }
