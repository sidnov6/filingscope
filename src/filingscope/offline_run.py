from __future__ import annotations

import argparse
import hashlib
from datetime import timedelta
from pathlib import Path

import httpx

from filingscope.filings import FilingDocumentParser
from filingscope.investigation.workflow import InvestigationInputs, InvestigationWorkflow
from filingscope.pipeline import DeterministicPipeline
from filingscope.reports import ReportRenderer
from filingscope.retrieval import FilingSearchIndex
from filingscope.schemas import FilingMetadata, SourceReference
from filingscope.sec.cache import RawResponseCache
from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FilingScope end to end from offline fixtures")
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--cik", default="0000320193")
    args = parser.parse_args()

    submissions = (args.fixtures / "aapl_submissions_excerpt.json").read_bytes()
    companyfacts = (args.fixtures / "aapl_companyfacts_excerpt.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = companyfacts if "companyfacts" in request.url.path else submissions
        return httpx.Response(200, content=payload, headers={"content-type": "application/json"})

    store = ParquetDuckDbStore(args.data_dir)
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        ingestion = SecIngestionService(
            SecHttpClient(
                user_agent="FilingScope offline fixture tests@filingscope.local",
                cache=RawResponseCache(args.data_dir),
                http_client=transport,
            ),
            store,
        ).ingest_company(args.cik)
    analysis = DeterministicPipeline(store).run(ingestion.company.cik, ingestion.facts)

    filing_payload = (args.fixtures / "aapl_2018_10k_excerpt.html").read_bytes()
    filing_hash = hashlib.sha256(filing_payload).hexdigest()
    source = SourceReference(
        source_type="sec_filing",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019318000145/a10-k20189292018.htm"
        ),
        content_sha256=filing_hash,
        manifest_id=filing_hash,
        retrieved_at=ingestion.manifests[0].retrieved_at,
        accession_number="0000320193-18-000145",
    )
    filing = FilingMetadata(
        accession_number="0000320193-18-000145",
        cik=ingestion.company.cik,
        form="10-K",
        filing_date="2018-11-05",
        report_period="2018-09-29",
        primary_document="a10-k20189292018.htm",
        source=source,
    )
    chunks = FilingDocumentParser().parse(
        filing_payload,
        filing,
        source,
        ticker=ingestion.company.tickers[0] if ingestion.company.tickers else None,
    )
    store.persist_filing_chunks(cik=ingestion.company.cik, chunks=list(chunks))
    FilingSearchIndex(args.data_dir / "filing-search.sqlite3").index(chunks)

    period_end = max(fact.period.end_date for fact in analysis.normalized_facts)
    period_start = period_end - timedelta(days=1_825)
    report = InvestigationWorkflow().run(
        InvestigationInputs(
            company=ingestion.company,
            requested_period_start=period_start,
            requested_period_end=period_end,
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
    store.persist_investigation_run(report.run)
    store.persist_agent_outputs(report)
    paths = ReportRenderer().write(report, args.data_dir / "reports")
    print(
        f"Completed {ingestion.company.legal_name}: {len(analysis.normalized_facts)} facts, "
        f"{len(analysis.tests)} tests, {len(analysis.signals)} signals, "
        f"{len(chunks)} filing chunks; report {paths['json']}"
    )


if __name__ == "__main__":
    main()
