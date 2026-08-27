from __future__ import annotations

from collections.abc import Iterable

from filingscope.errors import IdentityResolutionError
from filingscope.schemas import CompanyIdentity


def normalize_cik(value: str | int) -> str:
    raw = str(value).strip()
    if raw.upper().startswith("CIK"):
        raw = raw[3:]
    if not raw.isdigit() or len(raw) > 10:
        raise IdentityResolutionError(
            message=f"Invalid CIK: {value!r}",
            code="invalid_cik",
            details={"input": str(value)},
        )
    return raw.zfill(10)


class IdentityResolver:
    """Resolve an entity against an explicit CIK-backed identity set."""

    def __init__(self, identities: Iterable[CompanyIdentity]) -> None:
        self._identities = tuple(identities)

    def resolve(self, query: str | int) -> CompanyIdentity:
        raw = str(query).strip()
        if raw.upper().startswith("CIK") or raw.isdigit():
            cik = normalize_cik(raw)
            matches = [identity for identity in self._identities if identity.cik == cik]
        else:
            folded = raw.casefold()
            ticker_matches = [
                identity
                for identity in self._identities
                if any(ticker.casefold() == folded for ticker in identity.tickers)
            ]
            matches = ticker_matches or [
                identity
                for identity in self._identities
                if identity.legal_name.casefold() == folded
            ]

        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise IdentityResolutionError(
                message=f"No CIK-backed company identity matched {raw!r}",
                code="identity_not_found",
                details={"query": raw},
            )
        raise IdentityResolutionError(
            message=f"Company identity is ambiguous for {raw!r}",
            code="identity_ambiguous",
            details={"query": raw, "ciks": [identity.cik for identity in matches]},
        )
