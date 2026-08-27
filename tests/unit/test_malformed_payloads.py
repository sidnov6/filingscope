from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from filingscope.errors import SecPayloadError
from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService


class RecordingStore:
    def __init__(self) -> None:
        self.calls = 0

    def persist_ingestion(self, company, filings, facts) -> None:
        self.calls += 1


def test_malformed_json_is_preserved_but_not_parsed(
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    client = client_factory(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=b'{"broken":', headers={"content-type": "application/json"}
            )
        )
    )
    with pytest.raises(SecPayloadError) as error:
        client.fetch_json(
            "https://data.sec.gov/example.json", namespace="submissions", identity="0000320193"
        )
    assert error.value.code == "malformed_sec_json"
    assert list(client.cache.root.glob("raw/sec/submissions/**/*.json"))


def test_missing_required_companyfacts_fields_emit_no_derived_records(
    fixture_dir,
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    submissions = (fixture_dir / "aapl_submissions_excerpt.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        content = b'{"cik":320193,"entityName":"Apple Inc."}'
        if "submissions" in request.url.path:
            content = submissions
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    store = RecordingStore()
    service = SecIngestionService(client_factory(httpx.MockTransport(handler)), store)
    with pytest.raises(SecPayloadError) as error:
        service.ingest_company("AAPL" if False else "320193")
    assert error.value.code == "invalid_sec_payload"
    assert store.calls == 0
