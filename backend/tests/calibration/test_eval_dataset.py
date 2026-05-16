"""EvalCase dataset construction for Gong calibration."""

from app.calibration.dataset import EvalCase, build_case_record_eval_case
from app.knowledge.loader import load_library


def test_build_eval_case_from_factory_record_has_holdout_policy() -> None:
    library = load_library()
    record = next(r for r in library.cases if r.case_id == "DJGS-25-8-B001-0358-四方T帽-106S-过模图")

    eval_case = build_case_record_eval_case(record)

    assert isinstance(eval_case, EvalCase)
    assert eval_case.case_id == record.case_id
    assert eval_case.source_type == "factory_gt"
    assert eval_case.trust_level == "gold"
    assert eval_case.input_part_features == record.part_features
    assert eval_case.expected_process_forming == record.process_forming
    assert eval_case.holdout_case_ids == [record.case_id]
    assert "square_T_head" in eval_case.tags
    assert "trimming" in eval_case.tags
    assert "piercing" in eval_case.tags


def test_build_eval_case_from_standard_record_marks_standard_source() -> None:
    standard = load_library().standards[0]

    eval_case = build_case_record_eval_case(standard)

    assert eval_case.source_type == "standard_part"
    assert eval_case.trust_level == "reviewed"
    assert eval_case.holdout_case_ids == [standard.case_id]
