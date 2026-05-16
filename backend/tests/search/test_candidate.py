"""Search candidate contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.data.schemas import ConfidenceLevel, OperationType, PostProcess, WorkpieceGeometry
from app.search.candidate import (
    CandidatePlan,
    CandidateStation,
    ConstraintResult,
    ScoreBreakdown,
    SearchTrace,
)


def test_candidate_plan_serializes_and_converts_to_process_forming() -> None:
    blank = WorkpieceGeometry(
        type="cylinder",
        overall_length_mm=42.0,
        max_diameter_mm=6.0,
    )
    first_station = CandidateStation(
        n=1,
        operation=OperationType.upsetting,
        workpiece=WorkpieceGeometry(
            type="headed",
            overall_length_mm=38.0,
            max_diameter_mm=9.5,
            head_diameter_mm=9.5,
            head_height_mm=4.2,
            shank_diameter_mm=6.0,
            shank_length_mm=33.8,
        ),
        purpose_zh="聚集头部材料",
        key_dimensions={"head_D": 9.5},
    )
    candidate = CandidatePlan(
        candidate_id="square_t_cap_candidate_001",
        family="square_T_head",
        template_id="square_head_progression_v1",
        part_name_zh="四方T帽",
        material="10B21",
        blank=blank,
        stations=[first_station],
        post_processes=[PostProcess.thread_rolling],
        source_case_ids=["DJGS-25-8-B001-0358-四方T帽-106S-过模图"],
        constraint_results=[
            ConstraintResult(
                name="required_operation_coverage",
                passed=True,
                message="upsetting present before head forming",
            )
        ],
        score_breakdown=ScoreBreakdown(
            operation_coverage=0.8,
            precedence=0.7,
            deformation_safety=0.9,
            feature_progression=0.6,
            case_similarity=0.5,
            renderer_readiness=0.8,
        ),
        search_trace=SearchTrace(
            generated_by="unit_test",
            matched_features=["shank", "head"],
            applied_template_priors=["large head requires staged upsetting"],
            operation_choices=["station 1: upsetting"],
        ),
        rationale_zh="候选方案用于验证搜索中间合同。",
        confidence=ConfidenceLevel.medium,
    )

    payload = candidate.model_dump(mode="json")
    assert payload["candidate_id"] == "square_t_cap_candidate_001"
    assert payload["score_breakdown"]["total"] == 0.7167
    assert payload["search_trace"]["generated_by"] == "unit_test"

    forming = candidate.to_process_forming()
    assert forming.part_name_zh == "四方T帽"
    assert forming.station_count == 1
    assert forming.stations[0].operation == OperationType.upsetting
    assert forming.reasoning_zh == "候选方案用于验证搜索中间合同。"


def test_candidate_plan_rejects_non_contiguous_station_numbers() -> None:
    blank = WorkpieceGeometry(type="cylinder", overall_length_mm=42.0, max_diameter_mm=6.0)
    station = CandidateStation(
        n=2,
        operation=OperationType.upsetting,
        workpiece=WorkpieceGeometry(type="headed", overall_length_mm=38.0, max_diameter_mm=9.5),
    )

    with pytest.raises(ValidationError, match="station numbers must be contiguous"):
        CandidatePlan(
            candidate_id="bad_candidate",
            family="square_T_head",
            template_id="square_head_progression_v1",
            part_name_zh="四方T帽",
            material="10B21",
            blank=blank,
            stations=[station],
            score_breakdown=ScoreBreakdown(
                operation_coverage=0.8,
                precedence=0.7,
                deformation_safety=0.9,
                feature_progression=0.6,
                case_similarity=0.5,
                renderer_readiness=0.8,
            ),
            search_trace=SearchTrace(generated_by="unit_test"),
            rationale_zh="bad station sequence",
        )
