"""Candidate generation tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.schemas import OperationType, PartFeatures
from app.search.family_matcher import match_families
from app.search.features import ManufacturingFeatureGraph, build_feature_graph
from app.search.generator import generate_candidate_skeletons
from app.search.operations import (
    OperationCapability,
    OperationRequirement,
    OperationRequirements,
    infer_operation_requirements,
)


def test_square_t_cap_requirements_generate_candidate_skeleton() -> None:
    part = PartFeatures.model_validate(
        json.loads(
            Path("experiments/square_t_cap_holdout/input/part_features.json").read_text(
                encoding="utf-8"
            )
        )
    )
    graph = build_feature_graph(part)
    family = match_families(graph)[0]
    requirements = infer_operation_requirements(graph, family=family.family)

    candidates = generate_candidate_skeletons(
        graph=graph,
        family=family,
        requirements=requirements,
        max_candidates=3,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.family == "square_T_head"
    assert candidate.template_id == "square_T_head/dfs_skeleton"
    assert candidate.part_name_zh == graph.description
    assert candidate.search_trace.generated_by == "generic_dfs_skeleton_generator"

    operations = [station.operation for station in candidate.stations]
    assert operations == [
        OperationType.upsetting,
        OperationType.forward_extrusion,
        OperationType.heading,
        OperationType.combined,
        OperationType.trimming,
    ]
    assert "piercing optional: through_hole not present" in candidate.search_trace.warnings

    forming = candidate.to_process_forming()
    assert forming.station_count == 5
    assert forming.stations[-1].operation == OperationType.trimming


def test_generator_uses_requirement_precedence_for_non_special_family() -> None:
    graph = ManufacturingFeatureGraph(
        part_id="GENERIC-001",
        description="generic headed shaft",
        material="10B21",
        overall_length_mm=20.0,
    )
    requirements = OperationRequirements(
        family="generic_headed",
        required=[
            OperationRequirement(
                capability=OperationCapability.trimming_or_sizing,
                rationale_zh="final sizing",
                precedence_after=[OperationCapability.flange_forming],
            ),
            OperationRequirement(
                capability=OperationCapability.material_gathering,
                rationale_zh="gather stock",
            ),
            OperationRequirement(
                capability=OperationCapability.flange_forming,
                rationale_zh="form head",
                precedence_after=[OperationCapability.material_gathering],
            ),
        ],
    )
    family = match_families(graph)[0].model_copy(
        update={"family": "generic_headed", "score": 0.5}
    )

    candidates = generate_candidate_skeletons(
        graph=graph,
        family=family,
        requirements=requirements,
        max_candidates=3,
    )

    assert len(candidates) == 1
    assert candidates[0].template_id == "generic_headed/dfs_skeleton"
    assert [station.operation for station in candidates[0].stations] == [
        OperationType.upsetting,
        OperationType.heading,
        OperationType.trimming,
    ]
