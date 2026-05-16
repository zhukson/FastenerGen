"""Teacher-rationale checkpoint metrics for Gong calibration."""

from app.calibration.teacher_rationale import (
    OperationCheckpoint,
    PrecedenceCheckpoint,
    TeacherRationale,
    score_teacher_rationale_alignment,
)
from app.data.schemas import (
    ConfidenceLevel,
    OperationType,
    ProcessForming,
    StationStep,
    WorkpieceGeometry,
)


def test_teacher_rationale_scores_required_operations_and_precedence() -> None:
    rationale = TeacherRationale(
        case_id="square_t_cap",
        required_operations=[
            OperationCheckpoint(operation=OperationType.upsetting, why_zh="头部聚料"),
            OperationCheckpoint(operation=OperationType.forward_extrusion, why_zh="杆部正挤成形"),
            OperationCheckpoint(operation=OperationType.trimming, why_zh="四方头切边"),
            OperationCheckpoint(operation=OperationType.piercing, why_zh="冲通孔"),
        ],
        precedence_constraints=[
            PrecedenceCheckpoint(
                before=OperationType.trimming,
                after=OperationType.piercing,
                why_zh="GT 先切边再冲孔",
            )
        ],
    )
    predicted = _process_forming(
        [
            OperationType.upsetting,
            OperationType.heading,
            OperationType.trimming,
            OperationType.piercing,
        ]
    )

    metrics = score_teacher_rationale_alignment(predicted, rationale)
    by_name = {metric.metric_name: metric for metric in metrics}

    assert by_name["required_operation_recall"].value == 0.75
    assert by_name["required_operation_recall"].passed is False
    assert "missing: forward_extrusion" in by_name["required_operation_recall"].notes
    assert by_name["precedence_constraint_recall"].value == 1.0
    assert by_name["precedence_constraint_recall"].passed is True


def test_teacher_rationale_flags_wrong_precedence() -> None:
    rationale = TeacherRationale(
        case_id="square_t_cap",
        required_operations=[],
        precedence_constraints=[
            PrecedenceCheckpoint(
                before=OperationType.trimming,
                after=OperationType.piercing,
                why_zh="GT 先切边再冲孔",
            )
        ],
    )
    predicted = _process_forming([OperationType.piercing, OperationType.trimming])

    metrics = score_teacher_rationale_alignment(predicted, rationale)
    by_name = {metric.metric_name: metric for metric in metrics}

    assert by_name["precedence_constraint_recall"].value == 0.0
    assert by_name["precedence_constraint_recall"].passed is False
    assert "trimming before piercing" in by_name["precedence_constraint_recall"].notes


def _process_forming(operations: list[OperationType]) -> ProcessForming:
    stations = [
        StationStep(
            n=index,
            operation=operation,
            workpiece=WorkpieceGeometry(
                type="cylinder",
                overall_length_mm=10,
                max_diameter_mm=5,
            ),
            key_dimensions={"L": 10, "D": 5},
        )
        for index, operation in enumerate(operations, start=1)
    ]
    return ProcessForming(
        part_name_zh="fixture",
        material="10B21",
        blank=WorkpieceGeometry(type="cylinder", overall_length_mm=10, max_diameter_mm=5),
        stations=stations,
        reasoning_zh="fixture",
        cited_case_ids=[],
        confidence=ConfidenceLevel.medium,
    )
