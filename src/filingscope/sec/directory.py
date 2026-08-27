from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from filingscope.errors import SecPayloadError
from filingscope.sec.client import SecHttpClient
from filingscope.sec.identity import normalize_cik

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class CompanyDirectoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    cik: str = Field(pattern=r"^\d{10}$")
    ticker: str = Field(min_length=1)
    legal_name: str = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class CompanyDirectorySearch:
    entries: tuple[CompanyDirectoryEntry, ...]
    from_cache: bool


class SecCompanyDirectory:
    """Search the official SEC ticker directory through the controlled SEC client."""

    def __init__(self, client: SecHttpClient) -> None:
        self.client = client

    def search(self, query: str, *, limit: int = 12) -> CompanyDirectorySearch:
        payload, fetch = self.client.fetch_json(
            COMPANY_TICKERS_URL,
            namespace="company-directory",
            identity="company-tickers",
        )
        entries = parse_company_directory(payload)
        folded = query.strip().casefold()
        normalized_digits = normalize_cik(query) if query.strip().isdigit() else None

        def score(entry: CompanyDirectoryEntry) -> tuple[int, str, str]:
            ticker = entry.ticker.casefold()
            name = entry.legal_name.casefold()
            if normalized_digits == entry.cik:
                rank = 0
            elif ticker == folded:
                rank = 1
            elif name == folded:
                rank = 2
            elif ticker.startswith(folded):
                rank = 3
            elif name.startswith(folded):
                rank = 4
            elif folded in ticker:
                rank = 5
            else:
                rank = 6
            return rank, name, ticker

        matches = [
            entry
            for entry in entries
            if normalized_digits == entry.cik
            or folded in entry.ticker.casefold()
            or folded in entry.legal_name.casefold()
        ]
        return CompanyDirectorySearch(
            entries=tuple(sorted(matches, key=score)[:limit]),
            from_cache=fetch.from_cache,
        )


def parse_company_directory(payload: Any) -> tuple[CompanyDirectoryEntry, ...]:
    if not isinstance(payload, dict):
        raise SecPayloadError(
            message="SEC company directory was not an object",
            code="invalid_company_directory",
        )
    entries: list[CompanyDirectoryEntry] = []
    try:
        for row in payload.values():
            if not isinstance(row, dict):
                raise ValueError("directory row was not an object")
            entries.append(
                CompanyDirectoryEntry(
                    cik=normalize_cik(row["cik_str"]),
                    ticker=str(row["ticker"]).upper(),
                    legal_name=str(row["title"]),
                )
            )
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        raise SecPayloadError(
            message="SEC company directory failed schema validation",
            code="invalid_company_directory",
            details={"reason": str(error)},
        ) from error
    return tuple(entries)
