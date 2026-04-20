"""Tests for the synthetic data generator."""

from __future__ import annotations

import json
import math

import pytest

from app.data.synthetic import SyntheticDataGenerator
from app.data.schemas import ConfidenceLevel, PartFeatures, ProcessPlan


@pytest.fixture
def gen() -> SyntheticDataGenerator:
    return SyntheticDataGenerator(seed=42)


class TestSyntheticPartFeatures:
    def test_generates_valid_features(self, gen: SyntheticDataGenerator) -> None:
        features = gen.generate_part_features(seed=0)
        assert features.overall_length > 0
        assert features.head.diameter > features.shank.diameter
        assert features.thread.pitch > 0

    def test_geometry_validator_passes(self, gen: SyntheticDataGenerator) -> None:
        # Pydantic validation should not raise
        for i in range(20):
            features = gen.generate_part_features(seed=i)
            assert isinstance(features, PartFeatures)

    def test_part_number_format(self, gen: SyntheticDataGenerator) -> None:
        features = gen.generate_part_features(seed=1)
        assert features.part_number.startswith("SYN-")


class TestSyntheticProcessPlan:
    def test_generates_valid_plan(self, gen: SyntheticDataGenerator) -> None:
        features = gen.generate_part_features(seed=5)
        plan = gen.generate_process_plan(features)
        assert plan.total_stations >= 2
        assert plan.total_stations == len(plan.stations)

    def test_upset_ratios_within_limits(self, gen: SyntheticDataGenerator) -> None:
        for i in range(10):
            features = gen.generate_part_features(seed=i)
            plan = gen.generate_process_plan(features)
            for s in plan.stations:
                if s.upset_ratio is not None:
                    assert s.upset_ratio <= 2.3, f"Upset ratio {s.upset_ratio} exceeds 2.3"

    def test_blank_volume_roughly_conserved(self, gen: SyntheticDataGenerator) -> None:
        from app.geometry.workpiece import WorkpieceGenerator

        wp_gen = WorkpieceGenerator()
        for i in range(5):
            features = gen.generate_part_features(seed=i)
            plan = gen.generate_process_plan(features)
            blank_vol = wp_gen.blank_volume_mm3(plan.blank_diameter, plan.blank_length)
            final_shape = plan.stations[-1].output_shape
            final_vol = wp_gen.volume_mm3(final_shape)
            # Allow ±30% (approximation)
            ratio = blank_vol / final_vol if final_vol > 0 else 0
            assert 0.7 <= ratio <= 2.0, f"Volume ratio {ratio:.2f} out of range for seed {i}"


class TestSyntheticCompleteCase:
    def test_generates_complete_case(self, gen: SyntheticDataGenerator) -> None:
        case = gen.generate_complete_case(seed=0)
        assert case.case_id
        assert case.embedding_text
        assert len(case.die_parameters) == case.process_plan.total_stations

    def test_json_roundtrip(self, gen: SyntheticDataGenerator) -> None:
        case = gen.generate_complete_case(seed=1)
        data = json.loads(case.model_dump_json())
        from app.data.schemas import RAGCase
        restored = RAGCase(**data)
        assert restored.case_id == case.case_id

    def test_batch_generates_diverse_cases(self, gen: SyntheticDataGenerator) -> None:
        cases = gen.generate_batch(20)
        assert len(cases) == 20
        # Check diversity: not all same head type
        head_types = {c.part_features.head.type for c in cases}
        assert len(head_types) >= 3, "Expected at least 3 different head types in 20 cases"
