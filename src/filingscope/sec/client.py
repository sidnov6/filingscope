from __future__ import annotations

import json
import posixpath
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import structlog

from filingscope.errors import SecPayloadError, SecRequestError
from filingscope.schemas import RawFetchManifest
from filingscope.sec.cache import RawResponseCache

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_ALLOWED_HOSTS = frozenset({"data.sec.gov", "www.sec.gov", "sec.gov"})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_retries: int = 3
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 8.0
    jitter_seconds: float = 0.25


@dataclass(frozen=True, slots=True)
class FetchResult:
    payload: bytes
    manifest: RawFetchManifest
    from_cache: bool


class RateLimiter:
    def __init__(
        self,
        min_interval_seconds: float = 0.2,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_at: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_request_at is not None:
                remaining = self.min_interval_seconds - (now - self._last_request_at)
                if remaining > 0:
                    self._sleeper(remaining)
                    now = self._clock()
            self._last_request_at = now


class SecHttpClient:
    """Defensive SEC HTTP client with injectable transport and deterministic cache behavior."""

    def __init__(
        self,
        *,
        user_agent: str,
        cache: RawResponseCache,
        http_client: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float = 20.0,
        cache_max_age_seconds: int = 86_400,
        max_response_bytes: int = 50_000_000,
        sleeper: Callable[[float], None] = time.sleep,
        random_fn: Callable[[], float] = random.random,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if "@" not in user_agent or len(user_agent.strip()) < 12:
            raise ValueError("SEC User-Agent must identify the application and contact")
        self.user_agent = user_agent.strip()
        self.cache = cache
        self.http_client = http_client or httpx.Client(follow_redirects=False)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_policy = retry_policy or RetryPolicy()
        self.timeout_seconds = timeout_seconds
        self.cache_max_age_seconds = cache_max_age_seconds
        self.max_response_bytes = max_response_bytes
        self._sleep = sleeper
        self._random = random_fn
        self._now = now
        self._logger = structlog.get_logger(__name__)

    def fetch_json(
        self,
        url: str,
        *,
        namespace: str,
        identity: str,
        accession_number: str | None = None,
    ) -> tuple[Any, FetchResult]:
        result = self.fetch(
            url,
            namespace=namespace,
            identity=identity,
            accession_number=accession_number,
        )
        if result.manifest.http_status != 200:
            raise SecRequestError(
                message=f"SEC returned HTTP {result.manifest.http_status}",
                code="sec_http_error",
                details={"url": str(result.manifest.canonical_url)},
            )
        content_type = (result.manifest.content_type or "").casefold()
        if "json" not in content_type:
            raise SecPayloadError(
                message="SEC response was not JSON",
                code="unexpected_content_type",
                details={"content_type": result.manifest.content_type},
            )
        try:
            return json.loads(result.payload), result
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SecPayloadError(
                message="SEC response contained malformed JSON",
                code="malformed_sec_json",
                details={"manifest_id": result.manifest.manifest_id},
            ) from error

    def fetch(
        self,
        url: str,
        *,
        namespace: str,
        identity: str,
        accession_number: str | None = None,
    ) -> FetchResult:
        canonical_url = canonicalize_sec_url(url)
        cached = self.cache.lookup(canonical_url)
        now = self._now()
        if cached and self._is_fresh(cached.manifest, now):
            return FetchResult(cached.payload, cached.manifest, from_cache=True)

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.1",
        }
        if cached:
            if cached.manifest.etag:
                headers["If-None-Match"] = cached.manifest.etag
            if cached.manifest.last_modified:
                headers["If-Modified-Since"] = cached.manifest.last_modified

        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_retries + 2):
            self.rate_limiter.wait()
            try:
                response = self.http_client.get(
                    canonical_url,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except httpx.RequestError as error:
                last_error = error
                if attempt > self.retry_policy.max_retries:
                    break
                self._sleep(self._backoff(attempt, None))
                continue

            if response.status_code == 304 and cached:
                return FetchResult(cached.payload, cached.manifest, from_cache=True)

            content = response.content
            if len(content) > self.max_response_bytes:
                raise SecPayloadError(
                    message="SEC response exceeded configured size limit",
                    code="sec_response_too_large",
                    details={"bytes": len(content), "limit": self.max_response_bytes},
                )
            entry = self.cache.store(
                canonical_url=canonical_url,
                content=content,
                retrieved_at=now,
                http_status=response.status_code,
                content_type=response.headers.get("content-type"),
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                namespace=namespace,
                identity=identity,
                accession_number=accession_number,
                attempt_count=attempt,
                cacheable=response.status_code == 200,
            )
            if response.status_code not in _RETRYABLE_STATUS:
                return FetchResult(entry.payload, entry.manifest, from_cache=False)
            if attempt > self.retry_policy.max_retries:
                return FetchResult(entry.payload, entry.manifest, from_cache=False)
            self._logger.warning(
                "sec_request_retry",
                url=canonical_url,
                status=response.status_code,
                attempt=attempt,
            )
            self._sleep(self._backoff(attempt, response.headers.get("retry-after")))

        raise SecRequestError(
            message="SEC request failed after retry cap",
            code="sec_request_failed",
            details={"url": canonical_url, "reason": str(last_error)},
        ) from last_error

    def _is_fresh(self, manifest: RawFetchManifest, now: datetime) -> bool:
        return now - manifest.retrieved_at <= timedelta(seconds=self.cache_max_age_seconds)

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        retry_seconds = _parse_retry_after(retry_after, self._now())
        if retry_seconds is not None:
            return min(retry_seconds, self.retry_policy.max_backoff_seconds)
        exponential = self.retry_policy.base_backoff_seconds * (2 ** (attempt - 1))
        jitter = self.retry_policy.jitter_seconds * self._random()
        return float(min(exponential + jitter, self.retry_policy.max_backoff_seconds))


def canonicalize_sec_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold()
    if parts.scheme.casefold() != "https" or host not in _ALLOWED_HOSTS:
        raise SecRequestError(
            message="Outbound SEC URL is not allowlisted",
            code="sec_url_not_allowed",
            details={"url": url},
        )
    path = posixpath.normpath(parts.path or "/")
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit(("https", host, path, query, ""))


def _parse_retry_after(value: str | None, now: datetime) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(0.0, (retry_at - now).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
