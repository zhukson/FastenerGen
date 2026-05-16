"""Search candidate constraint tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.schemas import OperationType, PartFeatures
from app.search.constraints import evaluate_candidate_constraints
from app.search.family_matcher import match_families
from app.search.features import build_feature_graph
from app.search.generator import generate_candidate_skeletons
from app.search.operations import OperationCapability, infer_operation_requirements


def _square_t_cap_candidate_and_requirements():
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
    candidate = generate_candidate_skeletons(
        graph=graph,
        family=family,
        requirements=requirements,
        max_candidates=1,
    )[0]
    return candidate, requirements


def test_generated_square_t_cap_candidate_passes_required_constraints() -> None:
    candidate, requirements = _square_t_cap_candidate_and_requirements()

    result = evaluate_candidate_constraints(candidate, requirements)

    assert result.passed
    assert result.covered_capabilities >= {
        OperationCapability.material_gathering,
        OperationCapability.forward_extrusion,
        OperationCapability.flange_forming,
        OperationCapability.polygon_head_forming,
        OperationCapability.recess_forming,
        OperationCapability.trimming_or_sizing,
    }
    assert result.failure_tags == []


def test_constraints_report_missing_required_capability() -> None:
    candidate, requirements = _square_t_cap_candidate_and_requirements()
    candidate.stations = [
        station
        for station in candidate.stations
        if station.operation != OperationType.forward_extrusion
    ]
    for n, station in enumerate(candidate.stations, start=1):
        station.n = n

    result = evaluate_candidate_constraints(candidate, requirements)

    assert not result.passed
    assert "missing_required_operation" in result.failure_tags
    assert OperationCapability.forward_extrusion in result.missing_capabilities


def test_constraints_report_precedence_violation() -> None:
    candidate, requirements = _square_t_cap_candidate_and_requirements()
    trim_idx = next(
        idx for idx, station in enumerate(candidate.stations) if station.operation == OperationType.trimming
    )
    trim_station = candidate.stations.pop(trim_idx)
    candidate.stations.insert(0, trim_station)
    for n, station in enumerate(candidate.stations, start=1):
        station.n = n

    result = evaluate_candidate_constraints(candidate, requirements)

    assert not result.passed
    assert "wrong_precedence" in result.failure_tags
