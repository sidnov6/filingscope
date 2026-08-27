from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from filingscope import schemas


def test_all_initial_contracts_expose_versioned_json_schemas() -> None:
    models = [
        schemas.CompanyIdentity,
        schemas.FilingMetadata,
        schemas.RawFetchManifest,
        schemas.SourceReference,
        schemas.RawXbrlFact,
        schemas.NormalizedFinancialFact,
        schemas.FinancialPeriod,
        schemas.DataQualityFinding,
        schemas.MetricResult,
        schemas.ForensicTestResult,
        schemas.Signal,
        schemas.EvidencePacket,
        schemas.InvestigationRunMetadata,
        schemas.FilingChunk,
        schemas.AnomalyResult,
        schemas.PeerContext,
        schemas.InvestigationPlan,
        schemas.InvestigationClaim,
        schemas.AgentCase,
        schemas.ClaimVerification,
        schemas.VerificationBatch,
        schemas.FinalAssessment,
        schemas.InvestigationReport,
        schemas.AgentOutputRecord,
    ]
    for model in models:
        assert "schema_version" in model.model_json_schema()["properties"]


def test_missing_metric_input_is_explicit_not_zero_filled() -> None:
    period = schemas.FinancialPeriod(
        period_type="duration",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    result = schemas.MetricResult(
        metric_result_id="metric-result-001",
        metric_id="free_cash_flow",
        formula_version="1.0.0",
        period=period,
        status=schemas.ComputationStatus.NOT_COMPUTABLE,
        not_computable_reason="Capital expenditure fact is missing",
    )
    assert result.value is None
    with pytest.raises(ValidationError):
        schemas.MetricResult(
            metric_result_id="metric-result-002",
            metric_id="free_cash_flow",
            formula_version="1.0.0",
            period=period,
            status=schemas.ComputationStatus.NOT_COMPUTABLE,
        )


def test_source_reference_rejects_invalid_content_hash() -> None:
    with pytest.raises(ValidationError):
        schemas.SourceReference(
            source_type="sec_companyfacts",
            source_url="https://data.sec.gov/example.json",
            content_sha256="not-a-hash",
            manifest_id="manifest-0001",
            retrieved_at=datetime.now(UTC),
        )


def test_signal_language_uses_screening_severity() -> None:
    signal = schemas.Signal(
        signal_id="signal-000001",
        category="earnings_quality",
        test_id="cfo_vs_net_income",
        severity=schemas.SignalSeverity.MODERATE,
        materiality=Decimal("0.12"),
        persistence="recurring",
        data_confidence=Decimal("0.8"),
        evidence_requirements=("Item 7 cash flow discussion",),
        score=Decimal("0.54"),
        score_explanation="Screening priority only; requires filing evidence.",
        source_test_result_ids=("test-result-001",),
    )
    assert signal.severity == "moderate"
