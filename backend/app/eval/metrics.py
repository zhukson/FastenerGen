"""Metrics for Gong-style ProcessForming schema evaluation."""

from __future__ import annotations

from collections.abc import Iterable

from app.data.schemas import GongMetricResult, ProcessForming, StationStep


def score_station_count(predicted: ProcessForming, expected: ProcessForming) -> GongMetricResult:
    """Score whether predicted station count matches the held-out answer."""
    error = abs(predicted.station_count - expected.station_count)
    return GongMetricResult(
        metric_name="station_count_error",
        value=float(error),
        passed=error == 0,
        threshold=0.0,
    )


def score_operation_sequence(predicted: ProcessForming, expected: ProcessForming) -> GongMetricResult:
    """Levenshtein-style operation sequence similarity in [0, 1]."""
    pred_ops = [s.operation.value for s in predicted.stations]
    exp_ops = [s.operation.value for s in expected.stations]
    distance = _levenshtein(pred_ops, exp_ops)
    denom = max(len(pred_ops), len(exp_ops), 1)
    value = 1.0 - distance / denom
    return GongMetricResult(
        metric_name="operation_sequence_similarity",
        value=value,
        passed=value >= 0.75,
        threshold=0.75,
    )


def score_station_operation_alignment(
    predicted: ProcessForming,
    expected: ProcessForming,
) -> GongMetricResult:
    """Ratio of same-index stations with the same operation."""
    denom = max(expected.station_count, 1)
    matches = 0
    for pred_station, expected_station in zip(predicted.stations, expected.stations, strict=False):
        if pred_station.operation == expected_station.operation:
            matches += 1
    value = matches / denom
    return GongMetricResult(
        metric_name="station_operation_alignment",
        value=value,
        passed=value >= 0.70,
        threshold=0.70,
    )


def score_key_dimension_coverage(predicted: ProcessForming) -> GongMetricResult:
    """Ratio of stations that expose at least two key dimensions for downstream drawing."""
    matched = sum(1 for station in predicted.stations if len(station.key_dimensions) >= 2)
    value = _ratio(matched, predicted.station_count)
    return GongMetricResult(
        metric_name="key_dimension_coverage",
        value=value,
        passed=value >= 0.80,
        threshold=0.80,
    )


def score_renderer_geometry_readiness(predicted: ProcessForming) -> GongMetricResult:
    """Ratio of stations with enough semantic geometry to produce a non-trivial view."""
    matched = sum(1 for station in predicted.stations if _station_has_drawable_geometry(station))
    value = _ratio(matched, predicted.station_count)
    return GongMetricResult(
        metric_name="renderer_geometry_readiness",
        value=value,
        passed=value >= 0.80,
        threshold=0.80,
    )


def compute_process_forming_metrics(
    predicted: ProcessForming,
    expected: ProcessForming | None = None,
) -> list[GongMetricResult]:
    """Compute core metrics for one Gong reasoning run.

    Metrics that require a held-out answer key are emitted only when
    ``expected`` is provided. Schema-readiness metrics always run because they
    validate the handoff quality to FastenerDrawingEngine.
    """
    metrics = [
        score_key_dimension_coverage(predicted),
        score_renderer_geometry_readiness(predicted),
    ]
    if expected is not None:
        metrics = [
            score_station_count(predicted, expected),
            score_operation_sequence(predicted, expected),
            score_station_operation_alignment(predicted, expected),
            *metrics,
        ]
    return metrics


def aggregate_metric_mean(metric_name: str, results: Iterable[GongMetricResult]) -> GongMetricResult:
    matching = [r for r in results if r.metric_name == metric_name]
    value = sum(r.value for r in matching) / len(matching) if matching else 0.0
    return GongMetricResult(metric_name=f"{metric_name}_mean", value=value)


def _levenshtein(left: list[str], right: list[str]) -> int:
    if not left:
        return len(right)
    if not right:
        return len(left)
    prev = list(range(len(right) + 1))
    for i, lval in enumerate(left, start=1):
        curr = [i]
        for j, rval in enumerate(right, start=1):
            curr.append(
                min(
                    curr[j - 1] + 1,
                    prev[j] + 1,
                    prev[j - 1] + (0 if lval == rval else 1),
                )
            )
        prev = curr
    return prev[-1]


def _ratio(matched: int, total: int) -> float:
    return matched / total if total > 0 else 0.0


def _station_has_drawable_geometry(station: StationStep) -> bool:
    workpiece = station.workpiece
    if workpiece.profile_segments:
        return True
    if len(station.key_dimensions) >= 2:
        return True
    semantic_fields = (
        workpiece.head_diameter_mm,
        workpiece.head_height_mm,
        workpiece.shank_diameter_mm,
        workpiece.shank_length_mm,
        workpiece.head_recess_diameter_mm,
        workpiece.through_hole_diameter_mm,
        workpiece.corner_radius_mm,
        workpiece.chamfer_c_mm,
        workpiece.fillet_r_mm,
    )
    return sum(value is not None for value in semantic_fields) >= 2
