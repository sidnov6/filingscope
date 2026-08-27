from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from filingscope.schemas import (
    AnomalyResult,
    ComputationStatus,
    ForensicTestResult,
    Signal,
    SignalSeverity,
)


@dataclass(frozen=True, slots=True)
class SignalPolicy:
    robust_z_threshold: Decimal = Decimal("3.5")
    max_signals: int = 10


class SignalEngine:
    def __init__(self, policy: SignalPolicy | None = None) -> None:
        self.policy = policy or SignalPolicy()

    def rank(
        self,
        anomalies: Sequence[AnomalyResult],
        tests: Sequence[ForensicTestResult],
    ) -> tuple[Signal, ...]:
        test_by_metric: dict[str, ForensicTestResult] = {}
        for test in tests:
            if test.status != ComputationStatus.COMPUTED:
                continue
            metric_id = test.threshold_context.get("metric_id")
            if isinstance(metric_id, str):
                test_by_metric.setdefault(metric_id, test)
        signals: list[Signal] = []
        for anomaly in anomalies:
            robust_z = anomaly.robust_z_score
            matched_test = test_by_metric.get(anomaly.metric_id)
            if (
                robust_z is None
                or abs(robust_z) < self.policy.robust_z_threshold
                or matched_test is None
            ):
                continue
            confidence = matched_test.data_confidence or Decimal("0")
            score = min(abs(robust_z) / self.policy.robust_z_threshold, Decimal("2"))
            score = score * confidence / Decimal("2")
            evidence = matched_test.threshold_context.get("evidence_requirements", [])
            requirements = tuple(str(item) for item in evidence)
            materiality_change = (
                anomaly.year_over_year_change
                if anomaly.year_over_year_change is not None
                else anomaly.quarter_over_quarter_change
            )
            signals.append(
                Signal(
                    signal_id=_stable_id(matched_test.test_result_id, anomaly.anomaly_id),
                    category=str(matched_test.threshold_context.get("category", "other")),
                    test_id=matched_test.test_id,
                    severity=SignalSeverity.MODERATE,
                    materiality=(
                        abs(materiality_change) if materiality_change is not None else None
                    ),
                    persistence=anomaly.persistence,
                    data_confidence=confidence,
                    evidence_requirements=requirements,
                    score=score,
                    score_explanation=(
                        f"Moderate screening priority: |robust z|={abs(robust_z)} over "
                        f"{anomaly.sample_count} observations, threshold "
                        f"{self.policy.robust_z_threshold}, confidence {confidence}."
                    ),
                    source_test_result_ids=(matched_test.test_result_id,),
                )
            )
        return tuple(
            sorted(signals, key=lambda signal: (-signal.score, signal.signal_id))[
                : self.policy.max_signals
            ]
        )


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
