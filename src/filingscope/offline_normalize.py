from __future__ import annotations

import argparse
from pathlib import Path

import httpx

from filingscope.pipeline import DeterministicPipeline
from filingscope.sec.cache import RawResponseCache
from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and normalize deterministic SEC fixtures")
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
        client = SecHttpClient(
            user_agent="FilingScope offline fixture tests@filingscope.local",
            cache=RawResponseCache(args.data_dir),
            http_client=transport,
        )
        ingestion = SecIngestionService(client=client, store=store).ingest_company(args.cik)

    result = DeterministicPipeline(store).run(ingestion.company.cik, ingestion.facts)
    print(
        f"Analyzed {ingestion.company.legal_name}: {len(result.normalized_facts)} facts, "
        f"{len(result.findings)} findings, {len(result.metrics)} metric results, "
        f"{len(result.tests)} forensic tests, {len(result.signals)} signals, "
        f"mapping {result.mapping_version}"
    )


if __name__ == "__main__":
    main()
