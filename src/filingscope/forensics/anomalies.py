from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from statistics import median

from filingscope.schemas import AnomalyResult, ComputationStatus, MetricResult

ROBUST_Z_SCALE = Decimal("0.67448975")
MIN_ROBUST_SAMPLE = 4


class AnomalyEngine:
    def analyze(self, metrics: Sequence[MetricResult]) -> tuple[AnomalyResult, ...]:
        grouped: dict[str, list[MetricResult]] = defaultdict(list)
        for metric in metrics:
            if metric.status == ComputationStatus.COMPUTED and metric.value is not None:
                grouped[metric.metric_id].append(metric)
        anomalies: list[AnomalyResult] = []
        for metric_id, series in grouped.items():
            ordered = sorted(series, key=lambda result: result.period.end_date)
            for index, current in enumerate(ordered):
                history = ordered[: index + 1]
                values: list[Decimal] = []
                for result in history:
                    result_value = result.value
                    if result_value is not None:
                        values.append(result_value)
                current_value = current.value
                assert current_value is not None
                center = Decimal(str(median(values))) if values else None
                deviations: list[Decimal] = []
                if center is not None:
                    center_value: Decimal = center
                    deviations = [abs(value - center_value) for value in values]
                mad = Decimal(str(median(deviations))) if deviations else None
                robust_z = None
                if (
                    len(values) >= MIN_ROBUST_SAMPLE
                    and center is not None
                    and mad not in {None, Decimal("0")}
                ):
                    assert mad is not None
                    robust_z = ROBUST_Z_SCALE * (current_value - center) / mad
                previous = ordered[index - 1].value if index else None
                change = _relative_change(current_value, previous)
                percentile = _percentile(values, current_value)
                anomalies.append(
                    AnomalyResult(
                        anomaly_id=_stable_id(metric_id, current.metric_result_id),
                        metric_id=metric_id,
                        period=current.period,
                        current_value=current_value,
                        year_over_year_change=(
                            change if current.period.reporting_basis == "annual" else None
                        ),
                        quarter_over_quarter_change=(
                            change if current.period.reporting_basis == "quarterly" else None
                        ),
                        historical_median=center,
                        median_absolute_deviation=mad,
                        robust_z_score=robust_z,
                        rolling_percentile=percentile,
                        sample_count=len(values),
                        persistence=_persistence(values, center),
                        input_metric_result_ids=tuple(
                            result.metric_result_id for result in history
                        ),
                        explanation=(
                            f"Window contains {len(values)} observations; robust z-score "
                            + (
                                f"{robust_z} uses median/MAD."
                                if robust_z is not None
                                else "is unavailable until at least four non-constant values exist."
                            )
                        ),
                    )
                )
        return tuple(
            sorted(anomalies, key=lambda result: (result.metric_id, result.period.end_date))
        )


def _relative_change(current: Decimal, previous: Decimal | None) -> Decimal | None:
    if previous in {None, Decimal("0")}:
        return None
    assert previous is not None
    return (current - previous) / abs(previous)


def _percentile(values: list[Decimal], current: Decimal) -> Decimal:
    below_or_equal = sum(value <= current for value in values)
    return Decimal(below_or_equal) / Decimal(len(values))


def _persistence(values: list[Decimal], center: Decimal | None) -> str:
    if center is None or len(values) < 3:
        return "unknown"
    recent = values[-3:]
    distances = [abs(value - center) for value in recent]
    if distances[0] < distances[1] < distances[2]:
        return "worsening"
    same_side = all(value >= center for value in recent) or all(value <= center for value in recent)
    return "recurring" if same_side else "one_off"


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
