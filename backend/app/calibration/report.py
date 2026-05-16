"""Calibration reports for leave-one-out Gong reasoning runs."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.calibration.dataset import EvalCase
from app.calibration.teacher_rationale import (
    TeacherRationale,
    build_teacher_rationale_from_eval_case,
    score_teacher_rationale_alignment,
)
from app.data.schemas import GongMetricResult, ProcessForming
from app.eval.metrics import compute_process_forming_metrics


class CalibrationCaseReport(BaseModel):
    case_id: str
    source_type: str
    trust_level: str
    retrieved_case_ids: list[str] = Field(default_factory=list)
    metrics: list[GongMetricResult] = Field(default_factory=list)
    failure_tags: list[str] = Field(default_factory=list)


class CalibrationBatchReport(BaseModel):
    eval_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    case_count: int = Field(..., ge=0)
    metric_means: list[GongMetricResult] = Field(default_factory=list)
    failure_tag_counts: dict[str, int] = Field(default_factory=dict)
    case_reports: list[CalibrationCaseReport] = Field(default_factory=list)
    notes: str | None = None


def build_calibration_report(
    *,
    eval_case: EvalCase,
    predicted: ProcessForming,
    retrieved_case_ids: list[str] | None = None,
    teacher_rationale: TeacherRationale | None = None,
) -> CalibrationCaseReport:
    rationale = teacher_rationale or build_teacher_rationale_from_eval_case(eval_case)
    metrics = [
        *compute_process_forming_metrics(predicted, eval_case.expected_process_forming),
        *score_teacher_rationale_alignment(predicted, rationale),
    ]
    return CalibrationCaseReport(
        case_id=eval_case.case_id,
        source_type=eval_case.source_type,
        trust_level=eval_case.trust_level,
        retrieved_case_ids=retrieved_case_ids or [],
        metrics=metrics,
        failure_tags=_failure_tags(metrics),
    )


def build_batch_calibration_report(
    *,
    eval_id: str,
    case_reports: list[CalibrationCaseReport],
    notes: str | None = None,
) -> CalibrationBatchReport:
    """Aggregate per-case calibration reports into scorecard metrics."""
    metric_names = sorted(
        {metric.metric_name for report in case_reports for metric in report.metrics}
    )
    metric_means: list[GongMetricResult] = []
    for metric_name in metric_names:
        matching = [
            metric
            for report in case_reports
            for metric in report.metrics
            if metric.metric_name == metric_name
        ]
        if not matching:
            continue

        value = sum(metric.value for metric in matching) / len(matching)
        metric_means.append(
            GongMetricResult(
                metric_name=f"{metric_name}_mean",
                value=value,
            )
        )

        passable = [metric for metric in matching if metric.passed is not None]
        if passable:
            pass_rate = sum(1 for metric in passable if metric.passed) / len(passable)
            metric_means.append(
                GongMetricResult(
                    metric_name=f"{metric_name}_pass_rate",
                    value=pass_rate,
                )
            )

    tag_counts = Counter(
        tag for report in case_reports for tag in report.failure_tags
    )
    return CalibrationBatchReport(
        eval_id=eval_id,
        case_count=len(case_reports),
        metric_means=metric_means,
        failure_tag_counts=dict(sorted(tag_counts.items())),
        case_reports=case_reports,
        notes=notes,
    )


def _failure_tags(metrics: list[GongMetricResult]) -> list[str]:
    tags: set[str] = set()
    by_name = {metric.metric_name: metric for metric in metrics}
    if (metric := by_name.get("station_count_error")) and metric.value > 0:
        tags.add("station_count_error")
    if (metric := by_name.get("operation_sequence_similarity")) and metric.passed is False:
        tags.add("wrong_operation_sequence")
    if (metric := by_name.get("station_operation_alignment")) and metric.passed is False:
        tags.add("station_alignment_error")
    if (metric := by_name.get("required_operation_recall")) and metric.passed is False:
        tags.add("missing_required_operation")
    if (metric := by_name.get("precedence_constraint_recall")) and metric.passed is False:
        tags.add("wrong_precedence")
    if (metric := by_name.get("renderer_geometry_readiness")) and metric.passed is False:
        tags.add("schema_not_renderer_ready")
    return sorted(tags)
