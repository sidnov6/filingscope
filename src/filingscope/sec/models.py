from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SecPayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class RecentFilings(SecPayloadModel):
    accessionNumber: list[str]
    filingDate: list[date]
    reportDate: list[date | None]
    form: list[str]
    primaryDocument: list[str]

    @model_validator(mode="after")
    def validate_parallel_arrays(self) -> RecentFilings:
        sizes = {
            len(self.accessionNumber),
            len(self.filingDate),
            len(self.reportDate),
            len(self.form),
            len(self.primaryDocument),
        }
        if len(sizes) != 1:
            raise ValueError("SEC recent filing arrays have inconsistent lengths")
        return self


class FilingCollection(SecPayloadModel):
    recent: RecentFilings


class SubmissionsPayload(SecPayloadModel):
    cik: str | int
    entityType: str
    name: str = Field(min_length=1)
    tickers: list[str]
    exchanges: list[str]
    sic: str | int | None = None
    filings: FilingCollection


class CompanyFactUnit(SecPayloadModel):
    start: date | None = None
    end: date
    val: Decimal
    accn: str = Field(min_length=1)
    fy: int | None = None
    fp: str | None = None
    form: str = Field(min_length=1)
    filed: date
    frame: str | None = None
    decimals: int | None = None


class CompanyConcept(SecPayloadModel):
    label: str | None = None
    description: str | None = None
    units: dict[str, list[CompanyFactUnit]]


class CompanyFactsPayload(SecPayloadModel):
    cik: str | int
    entityName: str = Field(min_length=1)
    facts: dict[str, dict[str, CompanyConcept]]

    @model_validator(mode="before")
    @classmethod
    def require_fact_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("facts"), dict):
            raise ValueError("SEC Company Facts payload must contain a facts object")
        return value
