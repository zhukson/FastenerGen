"""Calibration report assembly from GT and teacher-rationale metrics."""

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.report import build_calibration_report
from app.calibration.teacher_rationale import (
    OperationCheckpoint,
    TeacherRationale,
)
from app.data.schemas import OperationType
from app.knowledge.loader import load_library


def test_calibration_report_combines_gt_and_teacher_metrics() -> None:
    record = next(
        r for r in load_library().cases
        if r.case_id == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    )
    eval_case = build_case_record_eval_case(record)
    predicted = record.process_forming.model_copy(deep=True)
    predicted.stations[1].operation = OperationType.heading

    report = build_calibration_report(
        eval_case=eval_case,
        predicted=predicted,
        retrieved_case_ids=["DJGS-22-2-四方通孔-105S-过模图"],
    )

    metric_names = {metric.metric_name for metric in report.metrics}
    assert "operation_sequence_similarity" in metric_names
    assert "required_operation_recall" in metric_names
    assert "precedence_constraint_recall" in metric_names
    assert report.case_id == eval_case.case_id
    assert report.retrieved_case_ids == ["DJGS-22-2-四方通孔-105S-过模图"]
    assert "missing_required_operation" in report.failure_tags


def test_calibration_report_can_use_persisted_teacher_rationale() -> None:
    record = next(
        r for r in load_library().cases
        if r.case_id == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    )
    eval_case = build_case_record_eval_case(record)
    persisted_rationale = TeacherRationale(
        case_id=record.case_id,
        required_operations=[
            OperationCheckpoint(
                operation=OperationType.backward_extrusion,
                why_zh="测试用持久化 checkpoint",
            )
        ],
    )

    report = build_calibration_report(
        eval_case=eval_case,
        predicted=record.process_forming,
        teacher_rationale=persisted_rationale,
    )

    required_recall = next(
        metric
        for metric in report.metrics
        if metric.metric_name == "required_operation_recall"
    )
    assert required_recall.passed is False
    assert required_recall.notes == "missing: backward_extrusion"
