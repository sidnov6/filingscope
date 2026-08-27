from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


@pytest.mark.integration
def test_fixture_ingestion_is_offline_idempotent_and_queryable(
    tmp_path: Path,
    fixture_dir: Path,
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    calls = 0
    submissions = (fixture_dir / "aapl_submissions_excerpt.json").read_bytes()
    companyfacts = (fixture_dir / "aapl_companyfacts_excerpt.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = companyfacts if "companyfacts" in request.url.path else submissions
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    client = client_factory(httpx.MockTransport(handler))
    store = ParquetDuckDbStore(tmp_path)
    service = SecIngestionService(client, store)
    first = service.ingest_company("320193")
    parquet_files = sorted((tmp_path / "warehouse").rglob("*.parquet"))
    mtimes = {path: path.stat().st_mtime_ns for path in parquet_files}
    second = service.ingest_company("0000320193")

    assert first.company.legal_name == "Apple Inc."
    assert len(first.filings) == 4
    assert len(first.facts) == 6
    assert first.cache_hits == 0
    assert second.cache_hits == 2
    assert calls == 2
    assert store.counts() == {"companies": 1, "filings": 4, "raw_xbrl_facts": 6}
    assert {path: path.stat().st_mtime_ns for path in parquet_files} == mtimes
    assert len(list((tmp_path / "raw/sec/manifests").glob("*.json"))) == 2
