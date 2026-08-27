from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from filingscope.schemas import (
    CompanyIdentity,
    ComputationStatus,
    MetricResult,
    PeerContext,
)


@dataclass(frozen=True, slots=True)
class PeerPolicy:
    min_peers: int
    min_confidence: Decimal
    min_asset_ratio: Decimal
    max_asset_ratio: Decimal


class PeerEngine:
    def compare(
        self,
        *,
        target: CompanyIdentity,
        metric: MetricResult,
        companies: Sequence[CompanyIdentity],
        metrics_by_cik: Mapping[str, Sequence[MetricResult]],
        policy: PeerPolicy | None,
    ) -> PeerContext:
        if policy is None:
            return self._unavailable(metric, "Peer size and quality policy is not configured")
        if not target.sic or metric.value is None:
            return self._unavailable(metric, "Target SIC or metric value is unavailable")
        target_assets = _aligned_value(metrics_by_cik.get(target.cik, ()), "assets", metric)
        if target_assets in {None, Decimal("0")}:
            return self._unavailable(metric, "Target assets are unavailable for size filtering")
        peers: list[tuple[str, Decimal]] = []
        for company in companies:
            if company.cik == target.cik or company.sic != target.sic:
                continue
            peer_metric = _aligned_result(
                metrics_by_cik.get(company.cik, ()), metric.metric_id, metric
            )
            peer_assets = _aligned_value(metrics_by_cik.get(company.cik, ()), "assets", metric)
            if (
                peer_metric is None
                or peer_metric.value is None
                or (peer_metric.data_confidence or Decimal("0")) < policy.min_confidence
                or peer_assets is None
            ):
                continue
            size_ratio = peer_assets / target_assets
            if policy.min_asset_ratio <= size_ratio <= policy.max_asset_ratio:
                peers.append((company.cik, peer_metric.value))
        if len(peers) < policy.min_peers:
            return self._unavailable(
                metric,
                f"Only {len(peers)} coherent SIC peers passed the explicit filters",
                peers,
            )
        values = sorted(value for _, value in peers)
        return PeerContext(
            metric_id=metric.metric_id,
            period=metric.period,
            status=ComputationStatus.COMPUTED,
            company_value=metric.value,
            peer_median=Decimal(str(median(values))),
            peer_first_quartile=_quantile(values, Decimal("0.25")),
            peer_third_quartile=_quantile(values, Decimal("0.75")),
            percentile=Decimal(sum(value <= metric.value for value in values))
            / Decimal(len(values)),
            peer_count=len(peers),
            peer_ciks=tuple(cik for cik, _ in sorted(peers)),
            reason="SIC, confidence, and asset-size filters were explicitly applied.",
        )

    @staticmethod
    def _unavailable(
        metric: MetricResult,
        reason: str,
        peers: Sequence[tuple[str, Decimal]] = (),
    ) -> PeerContext:
        return PeerContext(
            metric_id=metric.metric_id,
            period=metric.period,
            status=ComputationStatus.NOT_COMPUTABLE,
            company_value=metric.value,
            peer_count=len(peers),
            peer_ciks=tuple(cik for cik, _ in peers),
            reason=reason,
        )


def _aligned_result(
    results: Sequence[MetricResult], metric_id: str, anchor: MetricResult
) -> MetricResult | None:
    return next(
        (
            result
            for result in results
            if result.metric_id == metric_id
            and result.period.end_date == anchor.period.end_date
            and result.status == ComputationStatus.COMPUTED
        ),
        None,
    )


def _aligned_value(
    results: Sequence[MetricResult], metric_id: str, anchor: MetricResult
) -> Decimal | None:
    result = _aligned_result(results, metric_id, anchor)
    return result.value if result else None


def _quantile(values: list[Decimal], quantile: Decimal) -> Decimal:
    if len(values) == 1:
        return values[0]
    position = quantile * Decimal(len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - Decimal(lower)
    return values[lower] * (Decimal("1") - weight) + values[upper] * weight
