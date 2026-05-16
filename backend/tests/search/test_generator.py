"""Candidate generation tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.schemas import OperationType, PartFeatures
from app.search.family_matcher import match_families
from app.search.features import build_feature_graph
from app.search.generator import generate_candidate_skeletons
from app.search.operations import infer_operation_requirements


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
    assert candidate.template_id == "square_T_head/default_skeleton"
    assert candidate.part_name_zh == graph.description
    assert candidate.search_trace.generated_by == "template_guided_skeleton_generator"

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
