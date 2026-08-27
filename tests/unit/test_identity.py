from __future__ import annotations

import pytest

from filingscope.errors import IdentityResolutionError
from filingscope.schemas import CompanyIdentity
from filingscope.sec.identity import IdentityResolver, normalize_cik


def test_cik_normalization_and_ticker_resolution() -> None:
    apple = CompanyIdentity(cik="0000320193", legal_name="Apple Inc.", tickers=("aapl",))
    resolver = IdentityResolver([apple])
    assert normalize_cik(320193) == "0000320193"
    assert resolver.resolve("AAPL").cik == "0000320193"
    assert resolver.resolve("CIK320193").legal_name == "Apple Inc."


def test_unknown_ticker_does_not_become_an_identity() -> None:
    resolver = IdentityResolver([])
    with pytest.raises(IdentityResolutionError) as error:
        resolver.resolve("MISSING")
    assert error.value.code == "identity_not_found"


def test_ambiguous_ticker_fails_closed() -> None:
    resolver = IdentityResolver(
        [
            CompanyIdentity(cik="0000000001", legal_name="One", tickers=("SAME",)),
            CompanyIdentity(cik="0000000002", legal_name="Two", tickers=("SAME",)),
        ]
    )
    with pytest.raises(IdentityResolutionError) as error:
        resolver.resolve("same")
    assert error.value.code == "identity_ambiguous"
