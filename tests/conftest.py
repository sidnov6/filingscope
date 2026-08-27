from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from filingscope.sec.cache import RawResponseCache
from filingscope.sec.client import RateLimiter, SecHttpClient


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "sec"


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def client_factory(
    tmp_path: Path,
    fixed_now: datetime,
) -> Callable[[httpx.MockTransport], SecHttpClient]:
    def build(transport: httpx.MockTransport) -> SecHttpClient:
        return SecHttpClient(
            user_agent="FilingScope tests tests@filingscope.local",
            cache=RawResponseCache(tmp_path),
            http_client=httpx.Client(transport=transport),
            rate_limiter=RateLimiter(min_interval_seconds=0),
            sleeper=lambda _: None,
            random_fn=lambda: 0,
            now=lambda: fixed_now,
        )

    return build
