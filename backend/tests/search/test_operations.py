"""Operation grammar tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.schemas import PartFeatures
from app.search.features import build_feature_graph
from app.search.operations import OperationCapability, infer_operation_requirements


def test_square_t_cap_features_imply_required_operation_capabilities() -> None:
    part = PartFeatures.model_validate(
        json.loads(
            Path("experiments/square_t_cap_holdout/input/part_features.json").read_text(
                encoding="utf-8"
            )
        )
    )
    graph = build_feature_graph(part)

    requirements = infer_operation_requirements(graph, family="square_T_head")

    capabilities = {item.capability for item in requirements.required}
    assert OperationCapability.material_gathering in capabilities
    assert OperationCapability.forward_extrusion in capabilities
    assert OperationCapability.flange_forming in capabilities
    assert OperationCapability.polygon_head_forming in capabilities
    assert OperationCapability.recess_forming in capabilities
    assert OperationCapability.trimming_or_sizing in capabilities
    assert OperationCapability.piercing not in capabilities

    forward = requirements.require(OperationCapability.forward_extrusion)
    assert "cylindrical_shank" in forward.triggered_by_features
    assert "square_T_head" in forward.rationale_zh

    assert requirements.warnings == ["through_hole not present; piercing remains optional"]

