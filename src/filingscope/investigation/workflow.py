from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal, TypeVar

from pydantic import BaseModel

from filingscope.errors import InvestigationError
from filingscope.investigation.cache import AgentOutputCache
from filingscope.investigation.provider import ROLE_BUDGETS, StructuredProvider
from filingscope.schemas import (
    AgentCase,
    AnomalyResult,
    CompanyIdentity,
    DataQualityFinding,
    EvidencePacket,
    FinalAssessment,
    ForensicTestResult,
    InvestigationEvent,
    InvestigationPlan,
    InvestigationReport,
    InvestigationRunMetadata,
    InvestigationStatus,
    MetricResult,
    NormalizedFinancialFact,
    Signal,
    VerificationBatch,
    VerificationStatus,
)

PROMPT_VERSION = "1.4.0"
ModelT = TypeVar("ModelT", bound=BaseModel)
AgentRole = Literal["planner", "investigator", "bull", "skeptical", "verifier", "judge"]
EventRole = Literal["system", "planner", "investigator", "bull", "skeptical", "verifier", "judge"]
EventStatus = Literal["queued", "running", "complete", "skipped", "failed"]


@dataclass(frozen=True, slots=True)
class InvestigationInputs:
    company: CompanyIdentity
    requested_period_start: date
    requested_period_end: date
    findings: tuple[DataQualityFinding, ...]
    normalized_facts: tuple[NormalizedFinancialFact, ...]
    metrics: tuple[MetricResult, ...]
    tests: tuple[ForensicTestResult, ...]
    anomalies: tuple[AnomalyResult, ...]
    signals: tuple[Signal, ...]
    evidence: tuple[EvidencePacket, ...]
    mapping_version: str


class InvestigationWorkflow:
    def __init__(
        self,
        *,
        provider: StructuredProvider | None = None,
        cache: AgentOutputCache | None = None,
        max_signals: int = 8,
        max_evidence_packets: int = 12,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock_seconds: int = 180,
        on_event: Callable[[InvestigationEvent], None] | None = None,
    ) -> None:
        self.provider = provider
        self.cache = cache
        self.max_signals = max_signals
        self.max_evidence_packets = max_evidence_packets
        self.now = now
        self.monotonic = monotonic
        self.wall_clock_seconds = wall_clock_seconds
        self.on_event = on_event
        self._event_sequence = 0
        self._active_run_id = ""

    def run(self, inputs: InvestigationInputs) -> InvestigationReport:
        started_at = self.now()
        deadline = self.monotonic() + self.wall_clock_seconds
        signals = inputs.signals[: self.max_signals]
        evidence = inputs.evidence[: self.max_evidence_packets]
        configuration_hash = self._configuration_hash(inputs, signals, evidence)
        run_id = _stable_id(inputs.company.cik, configuration_hash)
        self._active_run_id = run_id
        self._event_sequence = 0
        self._emit(
            "system",
            "running",
            "Deterministic gate",
            f"Reviewed {len(signals)} ranked signals and {len(evidence)} evidence packets.",
        )
        if not signals:
            run = self._run_metadata(
                inputs,
                run_id,
                configuration_hash,
                started_at,
                InvestigationStatus.COMPLETE,
                "No ranked signals met the configured deterministic screening policy.",
                deterministic_only=True,
            )
            report = self._report(inputs, run, signals, evidence)
            self._emit(
                "system",
                "skipped",
                "Agent workflow not started",
                run.stop_reason or "No ranked signal qualified for investigation.",
            )
            return report
        if self.provider is None:
            run = self._run_metadata(
                inputs,
                run_id,
                configuration_hash,
                started_at,
                InvestigationStatus.PARTIAL,
                "Model provider unavailable; deterministic analysis and evidence are complete.",
                deterministic_only=True,
            )
            report = self._report(inputs, run, signals, evidence)
            self._emit(
                "system",
                "skipped",
                "Provider unavailable",
                run.stop_reason or "The deterministic analysis remains available.",
            )
            return report

        try:
            plan = self._complete(
                "planner",
                {
                    "company": inputs.company.model_dump(mode="json"),
                    "signals": [signal.model_dump(mode="json") for signal in signals],
                    "available_evidence_ids": [packet.evidence_id for packet in evidence],
                    "instruction": "Plan bounded questions; do not make findings.",
                },
                InvestigationPlan,
                deadline,
            )
            common = self._case_payload(inputs, signals, evidence, plan)
            investigator = self._normalize_case_references(
                self._complete(
                    "investigator",
                    {
                        **common,
                        "mandate": (
                            "Return one to three claims that collectively address every signal. "
                            "Reference only supplied metric or evidence IDs and identify evidence "
                            "gaps."
                        ),
                    },
                    AgentCase,
                    deadline,
                ),
                inputs,
                signals,
            )
            bull_case = self._normalize_case_references(
                self._complete(
                    "bull",
                    {
                        **common,
                        "mandate": (
                            "Return one to three supported claims forming the strongest legitimate "
                            "benign explanation. Reference only supplied metric or evidence IDs."
                        ),
                    },
                    AgentCase,
                    deadline,
                ),
                inputs,
                signals,
            )
            skeptical_case = self._normalize_case_references(
                self._complete(
                    "skeptical",
                    {
                        **common,
                        "mandate": (
                            "Return one to three supported claims testing whether "
                            "reporting quality is weaker than it appears. Reference only "
                            "supplied metric or evidence IDs."
                        ),
                    },
                    AgentCase,
                    deadline,
                ),
                inputs,
                signals,
            )
            for case, role in (
                (investigator, "investigator"),
                (bull_case, "bull"),
                (skeptical_case, "skeptical"),
            ):
                self._validate_case(case, role, inputs, signals, evidence)
            claims = (*investigator.claims, *bull_case.claims, *skeptical_case.claims)
            covered_signal_ids = {signal_id for claim in claims for signal_id in claim.signal_ids}
            if not {signal.signal_id for signal in signals}.issubset(covered_signal_ids):
                raise InvestigationError(
                    "Competing cases did not collectively address every ranked signal",
                    "agent_signal_coverage_failed",
                )
            verification_batch = self._complete(
                "verifier",
                {
                    "claims": [claim.model_dump(mode="json") for claim in claims],
                    "evidence": [
                        {
                            "evidence_id": packet.evidence_id,
                            "section": packet.section,
                            "excerpt": packet.excerpt,
                            "source": packet.source.model_dump(mode="json"),
                        }
                        for packet in evidence
                    ],
                    "instruction": "Verify each claim only against its exact cited references.",
                },
                VerificationBatch,
                deadline,
            )
            self._validate_verifications(claims, verification_batch, evidence)
            accepted_ids = {
                verification.claim_id
                for verification in verification_batch.verifications
                if verification.status
                in {VerificationStatus.SUPPORTED, VerificationStatus.PARTIALLY_SUPPORTED}
            }
            accepted_claims = [claim for claim in claims if claim.claim_id in accepted_ids]
            assessment = self._complete(
                "judge",
                {
                    "verified_or_partial_claims": [
                        claim.model_dump(mode="json") for claim in accepted_claims
                    ],
                    "verification_results": [
                        item.model_dump(mode="json") for item in verification_batch.verifications
                    ],
                    "instruction": (
                        "Use no new facts. Separate screening signals from evidence and include "
                        "limitations; do not allege fraud or provide investment advice."
                    ),
                },
                FinalAssessment,
                deadline,
            )
        except InvestigationError as error:
            run = self._run_metadata(
                inputs,
                run_id,
                configuration_hash,
                started_at,
                InvestigationStatus.PARTIAL,
                f"Agent workflow stopped safely: {error.code}.",
                deterministic_only=True,
            )
            report = self._report(inputs, run, signals, evidence)
            self._emit(
                "system",
                "failed",
                "Workflow stopped safely",
                run.stop_reason or "Typed validation stopped the workflow.",
            )
            return report

        run = self._run_metadata(
            inputs,
            run_id,
            configuration_hash,
            started_at,
            InvestigationStatus.COMPLETE,
            None,
            deterministic_only=False,
        )
        report = self._report(
            inputs,
            run,
            signals,
            evidence,
            plan=plan,
            investigator=investigator,
            bull_case=bull_case,
            skeptical_case=skeptical_case,
            verifications=verification_batch,
            assessment=assessment,
        )
        self._emit(
            "system",
            "complete",
            "Investigation complete",
            "All agent outputs passed typed validation and evidence verification.",
        )
        return report

    def _complete(
        self,
        role: AgentRole,
        payload: dict[str, object],
        model: type[ModelT],
        deadline: float,
    ) -> ModelT:
        if self.monotonic() >= deadline:
            raise InvestigationError(
                "Investigation exceeded its wall-clock budget",
                "investigation_wall_clock_exceeded",
            )
        assert self.provider is not None
        titles = {
            "planner": "Planning bounded questions",
            "investigator": "Testing the filing evidence",
            "bull": "Building the benign case",
            "skeptical": "Building the skeptical case",
            "verifier": "Checking every cited claim",
            "judge": "Weighing verified claims",
        }
        self._emit(role, "running", titles[role], "Structured provider call started.")
        material: dict[str, object] = {
            "role": role,
            "prompt_version": PROMPT_VERSION,
            "schema": model.__name__,
            "model": self.provider.model_name,
            "payload": payload,
        }
        key = AgentOutputCache.key(material)
        if self.cache:
            cached = self.cache.load(key, model)
            if cached is not None:
                self._emit(
                    role,
                    "complete",
                    titles[role],
                    "Validated output restored from cache.",
                    output=cached.model_dump(mode="json"),
                )
                return cached
        result = self.provider.complete(
            role=role,
            payload=payload,
            output_model=model,
            budget=ROLE_BUDGETS[role],
        )
        if self.cache:
            self.cache.store(key, result)
        self._emit(
            role,
            "complete",
            titles[role],
            "Validated structured output received.",
            output=result.model_dump(mode="json"),
        )
        return result

    def _emit(
        self,
        role: EventRole,
        status: EventStatus,
        title: str,
        message: str,
        *,
        output: dict[str, object] | None = None,
    ) -> None:
        if self.on_event is None:
            return
        self._event_sequence += 1
        self.on_event(
            InvestigationEvent(
                sequence=self._event_sequence,
                run_id=self._active_run_id,
                role=role,
                status=status,
                title=title,
                message=message,
                output=output,
                emitted_at=self.now(),
            )
        )

    @staticmethod
    def _case_payload(
        inputs: InvestigationInputs,
        signals: Sequence[Signal],
        evidence: Sequence[EvidencePacket],
        plan: BaseModel,
    ) -> dict[str, object]:
        metrics = InvestigationWorkflow._relevant_metrics(inputs, signals)
        return {
            "company": inputs.company.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "signals": [signal.model_dump(mode="json") for signal in signals],
            "metrics": [metric.model_dump(mode="json") for metric in metrics],
            "evidence": [
                {
                    "evidence_id": packet.evidence_id,
                    "section": packet.section,
                    "excerpt": packet.excerpt,
                    "source": packet.source.model_dump(mode="json"),
                    "untrusted_source_text": True,
                }
                for packet in evidence
            ],
        }

    @staticmethod
    def _normalize_case_references(
        case: AgentCase,
        inputs: InvestigationInputs,
        signals: Sequence[Signal],
    ) -> AgentCase:
        """Remove only metric IDs mistakenly duplicated into a claim's fact field."""
        allowed_facts = {fact.normalized_fact_id for fact in inputs.normalized_facts}
        allowed_metrics = {
            metric.metric_result_id
            for metric in InvestigationWorkflow._relevant_metrics(inputs, signals)
        }
        claims = []
        for claim in case.claims:
            invalid_facts = set(claim.fact_ids) - allowed_facts
            if invalid_facts and invalid_facts.issubset(allowed_metrics):
                claim = claim.model_copy(
                    update={
                        "fact_ids": tuple(
                            fact_id for fact_id in claim.fact_ids if fact_id in allowed_facts
                        )
                    }
                )
            claims.append(claim)
        return case.model_copy(update={"claims": tuple(claims)})

    @staticmethod
    def _validate_case(
        case: BaseModel,
        role: str,
        inputs: InvestigationInputs,
        signals: Sequence[Signal],
        evidence: Sequence[EvidencePacket],
    ) -> None:
        if not isinstance(case, AgentCase) or case.role != role:
            raise InvestigationError(
                message=f"{role} returned the wrong typed role",
                code="agent_role_mismatch",
            )
        signal_ids = {signal.signal_id for signal in signals}
        covered = {signal_id for claim in case.claims for signal_id in claim.signal_ids}
        if not covered:
            raise InvestigationError(
                message=f"{role} did not address any ranked signal",
                code="agent_signal_coverage_failed",
            )
        allowed_evidence = {packet.evidence_id for packet in evidence}
        allowed_facts = {fact.normalized_fact_id for fact in inputs.normalized_facts}
        allowed_metrics = {
            metric.metric_result_id
            for metric in InvestigationWorkflow._relevant_metrics(inputs, signals)
        }
        for claim in case.claims:
            if not set(claim.signal_ids).issubset(signal_ids):
                raise InvestigationError(
                    "Claim references an unknown signal", "claim_signal_invalid"
                )
            if not set(claim.evidence_ids).issubset(allowed_evidence):
                raise InvestigationError(
                    "Claim references evidence outside the exact packet", "claim_evidence_invalid"
                )
            if not set(claim.fact_ids).issubset(allowed_facts):
                raise InvestigationError("Claim references an unknown fact", "claim_fact_invalid")
            if not set(claim.metric_result_ids).issubset(allowed_metrics):
                raise InvestigationError(
                    "Claim references an unknown metric result", "claim_metric_invalid"
                )

    @staticmethod
    def _relevant_metrics(
        inputs: InvestigationInputs, signals: Sequence[Signal]
    ) -> tuple[MetricResult, ...]:
        test_ids = {
            test_result_id for signal in signals for test_result_id in signal.source_test_result_ids
        }
        metric_ids = {
            metric_result_id
            for test in inputs.tests
            if test.test_result_id in test_ids
            for metric_result_id in test.metric_result_ids
        }
        return tuple(metric for metric in inputs.metrics if metric.metric_result_id in metric_ids)

    @staticmethod
    def _validate_verifications(
        claims: Sequence[object],
        batch: BaseModel,
        evidence: Sequence[EvidencePacket],
    ) -> None:
        from filingscope.schemas import InvestigationClaim

        typed_claims = [claim for claim in claims if isinstance(claim, InvestigationClaim)]
        if not isinstance(batch, VerificationBatch):
            raise InvestigationError(
                "Verifier returned the wrong schema", "verifier_schema_invalid"
            )
        claim_by_id = {claim.claim_id: claim for claim in typed_claims}
        verified_ids = [item.claim_id for item in batch.verifications]
        if len(verified_ids) != len(set(verified_ids)) or set(verified_ids) != set(claim_by_id):
            raise InvestigationError(
                "Verifier must return exactly one result for every claim",
                "verifier_coverage_failed",
            )
        allowed_evidence = {packet.evidence_id for packet in evidence}
        for item in batch.verifications:
            claim = claim_by_id[item.claim_id]
            if not set(item.checked_evidence_ids).issubset(allowed_evidence):
                raise InvestigationError(
                    "Verifier referenced evidence outside the packet", "verifier_evidence_invalid"
                )
            if not set(item.checked_evidence_ids).issubset(set(claim.evidence_ids)):
                raise InvestigationError(
                    "Verifier checked evidence not cited by the claim",
                    "verifier_claim_scope_invalid",
                )

    def _run_metadata(
        self,
        inputs: InvestigationInputs,
        run_id: str,
        configuration_hash: str,
        started_at: datetime,
        status: InvestigationStatus,
        stop_reason: str | None,
        *,
        plan: BaseModel | None = None,
        deterministic_only: bool,
    ) -> InvestigationRunMetadata:
        manifests = tuple(sorted({fact.source.manifest_id for fact in inputs.normalized_facts}))
        return InvestigationRunMetadata(
            run_id=run_id,
            cik=inputs.company.cik,
            requested_period_start=inputs.requested_period_start,
            requested_period_end=inputs.requested_period_end,
            status=status,
            deterministic_only=deterministic_only,
            configuration_hash=configuration_hash,
            source_manifest_ids=manifests,
            mapping_version=inputs.mapping_version,
            prompt_version=PROMPT_VERSION if self.provider else None,
            model_metadata=(
                {"provider": "groq", "model": self.provider.model_name}
                if self.provider
                else {"provider": "not_used", "model": "not_used"}
            ),
            started_at=started_at,
            completed_at=self.now(),
            stop_reason=stop_reason,
        )

    @staticmethod
    def _report(
        inputs: InvestigationInputs,
        run: InvestigationRunMetadata,
        signals: Sequence[Signal],
        evidence: Sequence[EvidencePacket],
        *,
        plan: BaseModel | None = None,
        investigator: BaseModel | None = None,
        bull_case: BaseModel | None = None,
        skeptical_case: BaseModel | None = None,
        verifications: BaseModel | None = None,
        assessment: BaseModel | None = None,
    ) -> InvestigationReport:
        return InvestigationReport(
            run=run,
            company=inputs.company,
            findings=inputs.findings,
            metrics=inputs.metrics,
            tests=inputs.tests,
            anomalies=inputs.anomalies,
            signals=tuple(signals),
            evidence=tuple(evidence),
            plan=plan if isinstance(plan, InvestigationPlan) else None,
            investigator=investigator if isinstance(investigator, AgentCase) else None,
            bull_case=bull_case if isinstance(bull_case, AgentCase) else None,
            skeptical_case=skeptical_case if isinstance(skeptical_case, AgentCase) else None,
            verifications=(
                verifications.verifications if isinstance(verifications, VerificationBatch) else ()
            ),
            assessment=assessment if isinstance(assessment, FinalAssessment) else None,
            deterministic_only=run.deterministic_only,
        )

    def _configuration_hash(
        self,
        inputs: InvestigationInputs,
        signals: Sequence[Signal],
        evidence: Sequence[EvidencePacket],
    ) -> str:
        material = {
            "cik": inputs.company.cik,
            "period": [
                inputs.requested_period_start.isoformat(),
                inputs.requested_period_end.isoformat(),
            ],
            "mapping_version": inputs.mapping_version,
            "signals": [signal.signal_id for signal in signals],
            "evidence": [[packet.evidence_id, packet.source.content_sha256] for packet in evidence],
            "prompt_version": PROMPT_VERSION,
            "model": self.provider.model_name if self.provider else None,
            "max_signals": self.max_signals,
            "max_evidence_packets": self.max_evidence_packets,
        }
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
