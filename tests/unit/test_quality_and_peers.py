from __future__ import annotations

from datetime import date
from decimal import Decimal

from filingscope.analytics import PeerEngine, PeerPolicy
from filingscope.schemas import (
    CompanyIdentity,
    ComputationStatus,
    FinancialPeriod,
    MetricResult,
    PeriodBasis,
)


def _metric(metric_id: str, value: str, suffix: str) -> MetricResult:
    return MetricResult(
        metric_result_id=f"metric-{metric_id}-{suffix}",
        metric_id=metric_id,
        formula_version="1.0.0",
        period=FinancialPeriod(
            period_type="instant" if metric_id == "assets" else "duration",
            start_date=None if metric_id == "assets" else date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            fiscal_year=2025,
            fiscal_period="FY",
            reporting_basis=(PeriodBasis.INSTANT if metric_id == "assets" else PeriodBasis.ANNUAL),
        ),
        status=ComputationStatus.COMPUTED,
        value=Decimal(value),
        unit="USD" if metric_id == "assets" else "ratio",
        data_confidence=Decimal("0.9"),
    )


def test_peer_context_requires_explicit_policy_and_coherent_cohort() -> None:
    target = CompanyIdentity(cik="0000000001", legal_name="Target", sic="3571")
    peers = [
        CompanyIdentity(cik=f"{index:010d}", legal_name=f"Peer {index}", sic="3571")
        for index in range(2, 5)
    ]
    target_metric = _metric("gross_margin", "0.4", "target")
    metrics = {
        target.cik: [target_metric, _metric("assets", "100", "target")],
        **{
            peer.cik: [
                _metric("gross_margin", value, peer.cik),
                _metric("assets", size, peer.cik),
            ]
            for peer, value, size in zip(
                peers,
                ["0.3", "0.5", "0.6"],
                ["80", "120", "150"],
                strict=True,
            )
        },
    }
    engine = PeerEngine()
    unavailable = engine.compare(
        target=target,
        metric=target_metric,
        companies=[target, *peers],
        metrics_by_cik=metrics,
        policy=None,
    )
    result = engine.compare(
        target=target,
        metric=target_metric,
        companies=[target, *peers],
        metrics_by_cik=metrics,
        policy=PeerPolicy(
            min_peers=3,
            min_confidence=Decimal("0.8"),
            min_asset_ratio=Decimal("0.5"),
            max_asset_ratio=Decimal("2"),
        ),
    )

    assert unavailable.status == ComputationStatus.NOT_COMPUTABLE
    assert result.status == ComputationStatus.COMPUTED
    assert result.peer_median == Decimal("0.5")
    assert result.peer_count == 3
