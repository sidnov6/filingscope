from __future__ import annotations

import httpx

from filingscope.sec.client import RateLimiter, RetryPolicy, SecHttpClient


def test_rate_limiter_paces_sequential_requests() -> None:
    state = {"time": 0.0}
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        state["time"] += seconds

    limiter = RateLimiter(
        min_interval_seconds=0.25,
        clock=lambda: state["time"],
        sleeper=sleep,
    )
    limiter.wait()
    limiter.wait()
    assert sleeps == [0.25]


def test_retry_honors_retry_after_and_caps_attempts(
    tmp_path,
    fixed_now,
) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["user-agent"] == "FilingScope tests tests@filingscope.local"
        if attempts == 1:
            return httpx.Response(429, content=b"slow", headers={"retry-after": "1"})
        return httpx.Response(200, json={"ok": True})

    client = SecHttpClient(
        user_agent="FilingScope tests tests@filingscope.local",
        cache=__import__("filingscope.sec.cache", fromlist=["RawResponseCache"]).RawResponseCache(
            tmp_path
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        rate_limiter=RateLimiter(min_interval_seconds=0),
        retry_policy=RetryPolicy(max_retries=2, jitter_seconds=0),
        sleeper=sleeps.append,
        now=lambda: fixed_now,
    )
    payload, result = client.fetch_json(
        "https://data.sec.gov/example.json", namespace="submissions", identity="0000000001"
    )
    assert payload == {"ok": True}
    assert attempts == 2
    assert sleeps == [1.0]
    assert result.manifest.attempt_count == 2
