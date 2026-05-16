"""Family matching tests for primitive feature graphs."""

from __future__ import annotations

import json
from pathlib import Path

from app.data.schemas import PartFeatures
from app.search.family_matcher import match_families
from app.search.features import build_feature_graph


def test_square_t_cap_graph_matches_square_t_head_family_first() -> None:
    part = PartFeatures.model_validate(
        json.loads(
            Path("experiments/square_t_cap_holdout/input/part_features.json").read_text(
                encoding="utf-8"
            )
        )
    )
    graph = build_feature_graph(part)

    matches = match_families(graph)

    assert matches[0].family == "square_T_head"
    assert matches[0].score >= 0.8
    assert "square_head" in matches[0].matched_features
    assert "cylindrical_shank" in matches[0].matched_features
    assert "missing through_hole feature" in matches[0].warnings

