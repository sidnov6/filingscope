from __future__ import annotations

import argparse
from pathlib import Path

import httpx

from filingscope.sec.cache import RawResponseCache
from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic ingestion from SEC fixtures")
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--cik", default="0000320193")
    args = parser.parse_args()

    submissions = (args.fixtures / "aapl_submissions_excerpt.json").read_bytes()
    companyfacts = (args.fixtures / "aapl_companyfacts_excerpt.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = companyfacts if "companyfacts" in request.url.path else submissions
        return httpx.Response(200, content=payload, headers={"content-type": "application/json"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        client = SecHttpClient(
            user_agent="FilingScope offline fixture tests@filingscope.local",
            cache=RawResponseCache(args.data_dir),
            http_client=transport,
        )
        result = SecIngestionService(
            client=client,
            store=ParquetDuckDbStore(args.data_dir),
        ).ingest_company(args.cik)
    print(
        f"Ingested {result.company.legal_name}: "
        f"{len(result.filings)} filings, {len(result.facts)} raw facts, "
        f"{result.cache_hits} cache hits"
    )


if __name__ == "__main__":
    main()
