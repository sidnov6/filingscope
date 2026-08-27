from __future__ import annotations

import hashlib
from collections.abc import Callable

import httpx

from filingscope.sec.client import SecHttpClient


def test_manifest_hash_and_cache_hit_are_reproducible(
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    calls = 0
    content = b'{"cik":"0000320193"}'

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            content=content,
            headers={
                "content-type": "application/json",
                "etag": '"fixture-etag"',
                "last-modified": "Thu, 27 Aug 2026 10:00:00 GMT",
            },
        )

    client = client_factory(httpx.MockTransport(handler))
    first = client.fetch(
        "https://data.sec.gov/submissions/CIK0000320193.json",
        namespace="submissions",
        identity="0000320193",
    )
    second = client.fetch(
        "https://data.sec.gov/submissions/CIK0000320193.json",
        namespace="submissions",
        identity="0000320193",
    )
    assert first.manifest.content_sha256 == hashlib.sha256(content).hexdigest()
    assert first.manifest.byte_length == len(content)
    assert first.manifest.etag == '"fixture-etag"'
    assert first.manifest.accession_number is None
    assert second.from_cache is True
    assert second.manifest == first.manifest
    assert calls == 1


def test_corrupted_cached_payload_is_invalidated_and_refetched(
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"version": calls})

    client = client_factory(httpx.MockTransport(handler))
    first = client.fetch(
        "https://data.sec.gov/example.json", namespace="submissions", identity="0000320193"
    )
    payload_path = client.cache.root / first.manifest.relative_path
    payload_path.write_bytes(b"corrupted")
    second = client.fetch(
        "https://data.sec.gov/example.json", namespace="submissions", identity="0000320193"
    )
    assert calls == 2
    assert second.from_cache is False
    assert second.payload == b'{"version":2}'
