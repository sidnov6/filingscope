from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from filingscope.normalization import Normalizer, score_data_quality
from filingscope.sec.client import SecHttpClient
from filingscope.sec.ingestion import SecIngestionService
from filingscope.storage import ParquetDuckDbStore


@pytest.mark.integration
def test_fixture_normalization_matches_golden_and_is_idempotent(
    tmp_path: Path,
    fixture_dir: Path,
    client_factory: Callable[[httpx.MockTransport], SecHttpClient],
) -> None:
    submissions = (fixture_dir / "aapl_submissions_excerpt.json").read_bytes()
    companyfacts = (fixture_dir / "aapl_companyfacts_excerpt.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        content = companyfacts if "companyfacts" in request.url.path else submissions
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    store = ParquetDuckDbStore(tmp_path)
    ingestion = SecIngestionService(
        client_factory(httpx.MockTransport(handler)), store
    ).ingest_company("320193")
    result = Normalizer().normalize(ingestion.facts)
    actual = [
        {
            "canonical_metric": fact.canonical_metric,
            "value": str(fact.value),
            "unit": fact.unit,
            "start_date": (fact.period.start_date.isoformat() if fact.period.start_date else None),
            "end_date": fact.period.end_date.isoformat(),
            "reporting_basis": fact.period.reporting_basis,
            "form": fact.form,
            "accession_number": fact.accession_number,
        }
        for fact in result.facts
    ]
    expected = cast(
        list[dict[str, Any]],
        json.loads((fixture_dir / "aapl_normalized_expected.json").read_text()),
    )

    assert actual == expected
    assert {fact.original_concept for fact in result.facts} == {
        "Assets",
        "Revenues",
        "NetIncomeLoss",
    }
    assert all(fact.data_confidence == 1 for fact in result.facts)
    assert all(fact.mapping_version == "1.0.0" for fact in result.facts)
    assert all(fact.source.manifest_id for fact in result.facts)
    assert all(fact.accession_number in fact.selection_rationale for fact in result.facts)
    categories = [finding.category for finding in result.findings]
    assert categories.count("normalization_summary") == 1
    assert categories.count("missing_metric") == 28
    summary = next(
        finding for finding in result.findings if finding.category == "normalization_summary"
    )
    assert summary.source_references
    quality = score_data_quality(ingestion.company.cik, result.facts, result.findings)
    assert quality.completeness == Decimal(3) / Decimal(31)
    assert quality.reconciliation is None

    store.persist_normalization(
        cik=ingestion.company.cik,
        mapping_version=result.mapping_version,
        facts=list(result.facts),
        findings=list(result.findings),
    )
    parquet_files = sorted((tmp_path / "warehouse" / "normalized_facts").rglob("*.parquet"))
    parquet_files += sorted((tmp_path / "warehouse" / "data_quality_findings").rglob("*.parquet"))
    mtimes = {path: path.stat().st_mtime_ns for path in parquet_files}

    store.persist_normalization(
        cik=ingestion.company.cik,
        mapping_version=result.mapping_version,
        facts=list(result.facts),
        findings=list(result.findings),
    )

    assert store.normalization_counts() == {
        "normalized_facts": 6,
        "data_quality_findings": 29,
    }
    assert {path: path.stat().st_mtime_ns for path in parquet_files} == mtimes
