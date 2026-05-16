"""Generate deterministic teacher-rationale baselines from GT processes."""

from app.calibration.dataset import build_case_record_eval_case
from app.calibration.teacher_rationale import build_teacher_rationale_from_eval_case
from app.data.schemas import OperationType
from app.knowledge.loader import load_library


def test_teacher_rationale_from_gt_captures_required_ops_and_sequence() -> None:
    record = next(
        r for r in load_library().cases
        if r.case_id == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    )
    eval_case = build_case_record_eval_case(record)

    rationale = build_teacher_rationale_from_eval_case(eval_case)

    required_ops = {checkpoint.operation for checkpoint in rationale.required_operations}
    assert OperationType.forward_extrusion in required_ops
    assert OperationType.trimming in required_ops
    assert OperationType.piercing in required_ops
    assert any(
        constraint.before == OperationType.trimming
        and constraint.after == OperationType.piercing
        for constraint in rationale.precedence_constraints
    )
    assert all("GT 工序序列包含" not in item.why_zh for item in rationale.required_operations)
    assert all("GT 相邻工位顺序" not in item.why_zh for item in rationale.precedence_constraints)

    forward = next(
        checkpoint
        for checkpoint in rationale.required_operations
        if checkpoint.operation == OperationType.forward_extrusion
    )
    trimming = next(
        checkpoint
        for checkpoint in rationale.required_operations
        if checkpoint.operation == OperationType.trimming
    )
    assert "杆" in forward.why_zh
    assert "正挤" in forward.why_zh
    assert "四方" in trimming.why_zh
    assert "外轮廓" in trimming.why_zh


def test_square_head_teacher_rationale_contains_feature_observations() -> None:
    record = next(
        r for r in load_library().cases
        if r.case_id == "DJGS-25-8-B001-0358-四方T帽-106S-过模图"
    )

    rationale = build_teacher_rationale_from_eval_case(build_case_record_eval_case(record))

    observations = {item.feature_key: item for item in rationale.feature_observations}
    assert "square_or_t_head" in observations
    assert "large_head_volume" in observations
    assert "hole_or_recess" in observations
    assert any(
        "trimming" in inference
        for inference in observations["square_or_t_head"].expected_inference
    )
    assert any(
        "forward_extrusion" in inference
        for inference in observations["large_head_volume"].expected_inference
    )


def test_socket_cap_teacher_rationale_explains_backward_extrusion() -> None:
    record = next(
        r for r in load_library().standards
        if r.case_id == "BG30060-P03-DIN912-M20-P2-5"
    )

    rationale = build_teacher_rationale_from_eval_case(build_case_record_eval_case(record))

    backward = next(
        checkpoint
        for checkpoint in rationale.required_operations
        if checkpoint.operation == OperationType.backward_extrusion
    )
    assert "内六角" in backward.why_zh
    assert "反挤" in backward.why_zh
