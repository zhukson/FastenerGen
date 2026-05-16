"""Batch calibration aggregation across multiple case reports."""

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.report import (
    build_batch_calibration_report,
    build_calibration_report,
)
from app.data.schemas import OperationType
from app.knowledge.loader import load_library


def test_batch_calibration_report_aggregates_metrics_and_failure_tags() -> None:
    record = next(
        r for r in load_library().cases
        if r.case_id == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    )
    eval_case = build_case_record_eval_case(record)

    perfect = build_calibration_report(
        eval_case=eval_case,
        predicted=record.process_forming,
    )
    flawed_prediction = record.process_forming.model_copy(deep=True)
    flawed_prediction.stations[1].operation = OperationType.heading
    flawed = build_calibration_report(
        eval_case=eval_case,
        predicted=flawed_prediction,
    )

    batch = build_batch_calibration_report(
        eval_id="smoke",
        case_reports=[perfect, flawed],
        notes="offline smoke aggregate",
    )

    assert batch.eval_id == "smoke"
    assert batch.case_count == 2
    assert batch.notes == "offline smoke aggregate"
    assert batch.failure_tag_counts["missing_required_operation"] == 1

    means = {metric.metric_name: metric for metric in batch.metric_means}
    assert means["station_count_error_mean"].value == 0
    assert means["required_operation_recall_mean"].value < 1.0
    assert means["required_operation_recall_pass_rate"].value == 0.5
