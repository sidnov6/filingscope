from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from filingscope.analytics import MetricEngine
from filingscope.forensics import AnomalyEngine, ForensicEngine, SignalEngine
from filingscope.normalization import Normalizer
from filingscope.schemas import (
    AnomalyResult,
    DataQualityFinding,
    ForensicTestResult,
    MetricResult,
    NormalizedFinancialFact,
    RawXbrlFact,
    Signal,
)
from filingscope.storage import ParquetDuckDbStore


@dataclass(frozen=True, slots=True)
class DeterministicAnalysis:
    normalized_facts: tuple[NormalizedFinancialFact, ...]
    findings: tuple[DataQualityFinding, ...]
    metrics: tuple[MetricResult, ...]
    tests: tuple[ForensicTestResult, ...]
    anomalies: tuple[AnomalyResult, ...]
    signals: tuple[Signal, ...]
    mapping_version: str


class DeterministicPipeline:
    def __init__(self, store: ParquetDuckDbStore | None = None) -> None:
        self.store = store

    def run(self, cik: str, raw_facts: Sequence[RawXbrlFact]) -> DeterministicAnalysis:
        normalization = Normalizer().normalize(raw_facts)
        metrics = MetricEngine().calculate(normalization.facts)
        tests = ForensicEngine().run(metrics)
        anomalies = AnomalyEngine().analyze(metrics)
        signals = SignalEngine().rank(anomalies, tests)
        result = DeterministicAnalysis(
            normalized_facts=normalization.facts,
            findings=normalization.findings,
            metrics=metrics,
            tests=tests,
            anomalies=anomalies,
            signals=signals,
            mapping_version=normalization.mapping_version,
        )
        if self.store is not None:
            self.store.persist_normalization(
                cik=cik,
                mapping_version=result.mapping_version,
                facts=list(result.normalized_facts),
                findings=list(result.findings),
            )
            self.store.persist_analysis(
                cik=cik,
                metrics=list(result.metrics),
                tests=list(result.tests),
                anomalies=list(result.anomalies),
                signals=list(result.signals),
            )
        return result
