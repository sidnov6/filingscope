from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from pydantic import BaseModel

from filingscope.investigation.cache import AgentOutputCache
from filingscope.investigation.provider import GroqStructuredProvider, RoleBudget
from filingscope.investigation.workflow import InvestigationInputs, InvestigationWorkflow
from filingscope.reports import ReportRenderer
from filingscope.schemas import (
    AgentCase,
    AnomalyResult,
    ClaimVerification,
    CompanyIdentity,
    ComputationStatus,
    EvidencePacket,
    FinalAssessment,
    FinancialPeriod,
    ForensicTestResult,
    InvestigationClaim,
    InvestigationPlan,
    MetricResult,
    PeriodBasis,
    Signal,
    SignalSeverity,
    SourceReference,
    VerificationBatch,
    VerificationStatus,
)
from filingscope.storage import ParquetDuckDbStore


class FixtureProvider:
    model_name = "fixture-structured-model"

    def __init__(self, *, invalid_reference: bool = False) -> None:
        self.calls = 0
        self.invalid_reference = invalid_reference

    def complete(
        self,
        *,
        role: str,
        payload: dict[str, object],
        output_model: type[BaseModel],
        budget: RoleBudget,
    ) -> BaseModel:
        del output_model, budget
        self.calls += 1
        if role == "planner":
            return InvestigationPlan(
                plan_id="plan-fixture-001",
                signal_ids=("signal-fixture-001",),
                questions=("What evidence supports or contradicts the signal?",),
                evidence_requirements=("Item 9A controls",),
                stop_conditions=("Stop after the supplied evidence packet is assessed.",),
            )
        if role in {"investigator", "bull", "skeptical"}:
            evidence_id = (
                "E-NOT-ALLOWED" if self.invalid_reference and role == "bull" else "E-FIXTURE-001"
            )
            return AgentCase(
                role=role,
                claims=(
                    InvestigationClaim(
                        claim_id=f"claim-{role}-001",
                        role=role,
                        text=f"The {role} interpretation is limited to the supplied controls text.",
                        signal_ids=("signal-fixture-001",),
                        evidence_ids=(evidence_id,),
                        confidence=Decimal("0.7"),
                    ),
                ),
                evidence_gaps=("Only a sanitized filing excerpt is available.",),
                falsifiers=("A contradictory full-filing passage would change this view.",),
            )
        if role == "verifier":
            claims = payload["claims"]
            assert isinstance(claims, list)
            return VerificationBatch(
                verifications=tuple(
                    ClaimVerification(
                        claim_id=str(claim["claim_id"]),
                        status=VerificationStatus.SUPPORTED,
                        checked_evidence_ids=("E-FIXTURE-001",),
                        explanation="The claim is limited to the cited fixture passage.",
                    )
                    for claim in claims
                    if isinstance(claim, dict)
                )
            )
        if role == "judge":
            claims = payload["verified_or_partial_claims"]
            assert isinstance(claims, list)
            return FinalAssessment(
                assessment_id="assessment-001",
                summary="The supplied evidence supports only a limited controls observation.",
                strongest_concern=None,
                alternative_explanations=("The fixture is intentionally incomplete.",),
                verified_claim_ids=tuple(
                    str(claim["claim_id"]) for claim in claims if isinstance(claim, dict)
                ),
                unresolved_claim_ids=(),
                confidence=Decimal("0.6"),
                limitations=("The full filing was not included in this fixture.",),
                risk_language_disclosure=(
                    "A screening signal is not evidence of misconduct or investment advice."
                ),
            )
        raise AssertionError(role)


def _inputs(*, with_signal: bool = True) -> InvestigationInputs:
    period = FinancialPeriod(
        period_type="duration",
        start_date=date(2018, 1, 1),
        end_date=date(2018, 12, 31),
        fiscal_year=2018,
        fiscal_period="FY",
        reporting_basis=PeriodBasis.ANNUAL,
    )
    source = SourceReference(
        source_type="sec_filing",
        source_url="https://www.sec.gov/Archives/edgar/data/1/fixture.htm",
        content_sha256="c" * 64,
        manifest_id="manifest-investigation",
        retrieved_at=datetime(2026, 8, 27, tzinfo=UTC),
        accession_number="0000000001-18-000001",
    )
    metric = MetricResult(
        metric_result_id="metric-result-001",
        metric_id="gross_margin",
        formula_version="1.0.0",
        period=period,
        status=ComputationStatus.COMPUTED,
        value=Decimal("0.4"),
        unit="ratio",
        input_fact_ids=("normalized-fact-001",),
        data_confidence=Decimal("1"),
    )
    test = ForensicTestResult(
        test_result_id="test-result-001",
        test_id="gross_margin_volatility",
        test_version="1.0.0",
        period=period,
        status=ComputationStatus.COMPUTED,
        result=Decimal("0.4"),
        threshold_context={"metric_id": "gross_margin"},
        metric_result_ids=(metric.metric_result_id,),
        data_confidence=Decimal("1"),
        reason="Fixture diagnostic.",
    )
    signal = Signal(
        signal_id="signal-fixture-001",
        category="margins_costs",
        test_id=test.test_id,
        severity=SignalSeverity.MODERATE,
        materiality=Decimal("0.1"),
        persistence="one_off",
        data_confidence=Decimal("1"),
        evidence_requirements=("Item 9A controls",),
        score=Decimal("0.5"),
        score_explanation="Fixture screening priority.",
        source_test_result_ids=(test.test_result_id,),
    )
    evidence = EvidencePacket(
        evidence_id="E-FIXTURE-001",
        signal_id=signal.signal_id,
        source=source,
        section="Item 9A",
        chunk_id="chunk-fixture-001",
        start_offset=0,
        end_offset=25,
        excerpt="Controls were effective.",
        relevance_score=Decimal("1"),
        selection_reason="Fixture lexical match.",
        parser_version="1.0.0",
        token_count=3,
    )
    anomaly = AnomalyResult(
        anomaly_id="anomaly-fixture-001",
        metric_id="gross_margin",
        period=period,
        current_value=Decimal("0.4"),
        robust_z_score=Decimal("4"),
        sample_count=4,
        persistence="one_off",
        input_metric_result_ids=(metric.metric_result_id,),
        explanation="Fixture anomaly.",
    )
    return InvestigationInputs(
        company=CompanyIdentity(cik="0000000001", legal_name="Fixture Company", tickers=("FIX",)),
        requested_period_start=date(2018, 1, 1),
        requested_period_end=date(2018, 12, 31),
        findings=(),
        normalized_facts=(),
        metrics=(metric,),
        tests=(test,),
        anomalies=(anomaly,),
        signals=(signal,) if with_signal else (),
        evidence=(evidence,) if with_signal else (),
        mapping_version="1.0.0",
    )


def test_typed_workflow_caches_validated_outputs_and_renders_report(tmp_path: Path) -> None:
    provider = FixtureProvider()

    def fixed_now() -> datetime:
        return datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

    workflow = InvestigationWorkflow(
        provider=provider,
        cache=AgentOutputCache(tmp_path / "agent-cache"),
        now=fixed_now,
    )

    first = workflow.run(_inputs())
    second = workflow.run(_inputs())

    assert first.run.status == "complete"
    assert not first.deterministic_only
    assert len(first.verifications) == 3
    assert provider.calls == 6
    assert second == first

    paths = ReportRenderer().write(first, tmp_path / "reports")
    markdown = paths["markdown"].read_text()
    assert "E-FIXTURE-001" in markdown
    assert "does not establish fraud" in markdown
    assert ReportRenderer.read(paths["json"]) == first
    assert paths["audit"].exists()

    store = ParquetDuckDbStore(tmp_path / "stored")
    store.persist_agent_outputs(first)
    assert {output.role for output in store.agent_outputs(first.run.run_id)} == {
        "planner",
        "investigator",
        "bull",
        "skeptical",
        "verifier",
        "judge",
    }


def test_invalid_agent_reference_fails_closed_without_judgment() -> None:
    report = InvestigationWorkflow(provider=FixtureProvider(invalid_reference=True)).run(_inputs())

    assert report.run.status == "partial"
    assert report.deterministic_only
    assert report.assessment is None
    assert report.run.stop_reason == "Agent workflow stopped safely: claim_evidence_invalid."


def test_provider_unavailable_and_no_signal_degrade_honestly() -> None:
    unavailable = InvestigationWorkflow().run(_inputs())
    no_signal = InvestigationWorkflow(provider=FixtureProvider()).run(_inputs(with_signal=False))

    assert unavailable.run.status == "partial"
    assert unavailable.deterministic_only
    assert no_signal.run.status == "complete"
    assert no_signal.deterministic_only
    assert "No ranked signals" in (no_signal.run.stop_reason or "")


def test_workflow_emits_public_stage_events_without_private_reasoning() -> None:
    events = []
    report = InvestigationWorkflow(
        provider=FixtureProvider(),
        on_event=events.append,
        now=lambda: datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
    ).run(_inputs())

    assert report.run.status == "complete"
    assert [event.role for event in events if event.status == "complete"] == [
        "planner",
        "investigator",
        "bull",
        "skeptical",
        "verifier",
        "judge",
        "system",
    ]
    assert events[0].title == "Deterministic gate"
    assert events[-1].output is None


def test_workflow_wall_clock_budget_fails_closed_before_provider_call() -> None:
    ticks = iter((0.0, 181.0))
    provider = FixtureProvider()
    report = InvestigationWorkflow(
        provider=provider,
        monotonic=lambda: next(ticks),
        wall_clock_seconds=180,
    ).run(_inputs())

    assert report.run.status == "partial"
    assert report.run.stop_reason == (
        "Agent workflow stopped safely: investigation_wall_clock_exceeded."
    )
    assert provider.calls == 0


def test_groq_adapter_retries_then_validates_structured_output() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        content = InvestigationPlan(
            plan_id="plan-fixture-001",
            signal_ids=("signal-fixture-001",),
            questions=("What supports the signal?",),
            evidence_requirements=("Item 9A",),
            stop_conditions=("Stop after supplied evidence.",),
        ).model_dump_json()
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": content}}]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = GroqStructuredProvider(
            api_key="test-key",
            model_name="fixture-model",
            http_client=client,
            max_retries=1,
        )
        result = provider.complete(
            role="planner",
            payload={"signals": ["signal-fixture-001"]},
            output_model=InvestigationPlan,
            budget=RoleBudget(max_input_tokens=100, max_output_tokens=100),
        )

    assert result.plan_id == "plan-fixture-001"
    assert calls == 2
