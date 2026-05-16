"""Manufacturing feature graph tests."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.schemas import PartFeatures
from app.search.features import FeatureKind, build_feature_graph


def test_square_t_cap_part_features_become_primitive_feature_graph() -> None:
    payload = json.loads(
        Path("experiments/square_t_cap_holdout/input/part_features.json").read_text(
            encoding="utf-8"
        )
    )
    part = PartFeatures.model_validate(payload)

    graph = build_feature_graph(part)

    assert graph.part_id == "DJGS-25-8-B001-0358"
    assert graph.material == "106S"
    assert graph.overall_length_mm == 17.0

    kinds = {feature.kind for feature in graph.features}
    assert FeatureKind.cylindrical_shank in kinds
    assert FeatureKind.flange in kinds
    assert FeatureKind.square_head in kinds
    assert FeatureKind.corner_radius in kinds
    assert FeatureKind.cross_recess in kinds

    square = graph.require_feature(FeatureKind.square_head)
    assert square.dimensions_mm["flat_width"] == 17.65
    assert square.dimensions_mm["corner_radius"] == 2.5
    assert square.confidence == "medium"

    recess = graph.require_feature(FeatureKind.cross_recess)
    assert recess.source == "notes"

    assert graph.has_relation("square_head", "sits_on", "cylindrical_shank")
    assert graph.warnings == []

