"""
Tests for all Pydantic data schemas.

Verifies that every model can be instantiated with example data and
serialized to/from JSON. Based on the M6×33 flat head bolt (18149-D6).
"""

import json
from datetime import datetime

import pytest

from app.data.schemas import (
    CheckSeverity,
    ConfidenceLevel,
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    DesignResult,
    DesignStatus,
    EvalReport,
    ExpectedDecisions,
    ExtractedDimension,
    FileFormat,
    HeadFeatures,
    HeadType,
    MetricResult,
    OperationType,
    OutputFile,
    ParsedDrawing,
    PartFeatures,
    PostProcess,
    ProcessPlan,
    PseudoReasoning,
    RAGCase,
    RetrievedCase,
    ShankFeatures,
    ShapeDescription,
    StationPlan,
    TailFeatures,
    TailType,
    ThreadFeatures,
    TitleBlock,
    Tolerance,
    VerificationCheck,
    VerificationResult,
)


# --- Fixture: M6×33 Flat Head Bolt ---

@pytest.fixture
def m6x33_flat_head() -> PartFeatures:
    return PartFeatures(
        part_number="18149-D6",
        description="M6×33 Flat Head Bolt",
        overall_length=33.0,
        head=HeadFeatures(
            type=HeadType.flat,
            diameter=12.0,
            height=3.6,
            chamfer_angle_deg=90.0,
            chamfer_diameter=12.0,
            drive_type="cross",
            drive_size=3.0,
            underhead_radius=0.3,
        ),
        shank=ShankFeatures(diameter=6.0, length=8.0),
        thread=ThreadFeatures(
            spec="M6×1.0",
            nominal_diameter=6.0,
            pitch=1.0,
            length=20.0,
            thread_class="6g",
        ),
        material_grade="10B21",
        strength_grade="8.8",
        hardness_min_hv=250.0,
        hardness_max_hv=320.0,
        surface_treatment="zinc_plating_8um",
        standard="GB/T 5789",
    )


@pytest.fixture
def sample_process_plan(m6x33_flat_head: PartFeatures) -> ProcessPlan:
    blank_shape = ShapeDescription(
        overall_length=38.0, max_diameter=6.2,
        shank_diameter=6.2, shank_length=38.0,
    )
    after_s1 = ShapeDescription(
        overall_length=36.0, max_diameter=7.5,
        head_diameter=7.5, head_height=2.0,
        shank_diameter=6.0, shank_length=34.0,
    )
    after_s2 = ShapeDescription(
        overall_length=34.5, max_diameter=12.0,
        head_diameter=12.0, head_height=4.0,
        shank_diameter=6.0, shank_length=30.5,
    )

    return ProcessPlan(
        total_stations=2,
        blank_diameter=6.2,
        blank_length=38.0,
        stations=[
            StationPlan(
                station_number=1,
                operation=OperationType.upsetting,
                description="Pre-form upsetting — create head blank",
                input_shape=blank_shape,
                output_shape=after_s1,
                upset_ratio=1.21,
            ),
            StationPlan(
                station_number=2,
                operation=OperationType.heading,
                description="Finish heading — form flat head to final dimensions",
                input_shape=after_s1,
                output_shape=after_s2,
                upset_ratio=1.6,
            ),
        ],
        post_processes=[PostProcess.thread_rolling, PostProcess.zinc_plating],
        confidence=ConfidenceLevel.high,
        reasoning_summary=(
            "2-station process: pre-form upset + finish heading. "
            "Flat head with 90° countersink requires precise heading in station 2."
        ),
    )


@pytest.fixture
def sample_die_params() -> list[DieParameters]:
    punch_s1 = DieComponentParams(
        component_type="punch",
        material="SKD11",
        hardness_hrc_min=60.0,
        hardness_hrc_max=62.0,
        geometry_type=DieGeometryType.flat_face,
        outer_diameter=20.0,
        working_length=40.0,
        surface_roughness_ra=0.4,
    )
    die_s1 = DieComponentParams(
        component_type="die",
        material="SKD11",
        hardness_hrc_min=60.0,
        hardness_hrc_max=62.0,
        geometry_type=DieGeometryType.open_heading,
        outer_diameter=40.0,
        inner_diameter=6.22,
        working_length=35.0,
        cavity_depth=5.0,
        approach_angle_deg=15.0,
        land_length=3.0,
        surface_roughness_ra=0.2,
        surface_treatment="TiN",
        coating_thickness_um=3.0,
    )
    punch_s2 = DieComponentParams(
        component_type="punch",
        material="DC53",
        hardness_hrc_min=62.0,
        hardness_hrc_max=64.0,
        geometry_type=DieGeometryType.conical,
        outer_diameter=20.0,
        working_length=42.0,
        approach_angle_deg=90.0,
        surface_roughness_ra=0.2,
        surface_treatment="TiN",
        coating_thickness_um=3.0,
    )
    die_s2 = DieComponentParams(
        component_type="die",
        material="DC53",
        hardness_hrc_min=62.0,
        hardness_hrc_max=64.0,
        geometry_type=DieGeometryType.closed_heading,
        outer_diameter=40.0,
        inner_diameter=6.01,
        working_length=32.0,
        cavity_depth=4.2,
        approach_angle_deg=90.0,
        land_length=2.0,
        surface_roughness_ra=0.2,
        surface_treatment="TiCN",
        coating_thickness_um=3.0,
    )
    return [
        DieParameters(station_number=1, punch=punch_s1, die=die_s1, clearance_mm=0.11,
                      expected_life_shots=100_000),
        DieParameters(station_number=2, punch=punch_s2, die=die_s2, clearance_mm=0.05,
                      expected_life_shots=80_000),
    ]


# --- Tests ---

class TestTolerance:
    def test_instantiate(self) -> None:
        t = Tolerance(nominal=6.0, plus=0.0, minus=0.018)
        assert t.upper == 6.0
        assert t.lower == pytest.approx(5.982)

    def test_json_roundtrip(self) -> None:
        t = Tolerance(nominal=6.0, plus=0.0, minus=0.018)
        data = json.loads(t.model_dump_json())
        t2 = Tolerance(**data)
        assert t2.nominal == t.nominal


class TestPartFeatures:
    def test_m6x33_instantiate(self, m6x33_flat_head: PartFeatures) -> None:
        assert m6x33_flat_head.part_number == "18149-D6"
        assert m6x33_flat_head.overall_length == 33.0
        assert m6x33_flat_head.head.type == HeadType.flat

    def test_json_roundtrip(self, m6x33_flat_head: PartFeatures) -> None:
        data = json.loads(m6x33_flat_head.model_dump_json())
        restored = PartFeatures(**data)
        assert restored.part_number == m6x33_flat_head.part_number

    def test_geometry_validator_rejects_invalid(self) -> None:
        with pytest.raises(ValueError, match="exceeds overall_length"):
            PartFeatures(
                part_number="BAD",
                description="bad",
                overall_length=10.0,  # too short
                head=HeadFeatures(type=HeadType.hex, diameter=12.0, height=5.0),
                shank=ShankFeatures(diameter=6.0, length=30.0),
                thread=ThreadFeatures(
                    spec="M6×1.0", nominal_diameter=6.0, pitch=1.0,
                    length=20.0, thread_class="6g",
                ),
                material_grade="10B21",
                strength_grade="8.8",
            )


class TestProcessPlan:
    def test_instantiate(self, sample_process_plan: ProcessPlan) -> None:
        assert sample_process_plan.total_stations == 2
        assert len(sample_process_plan.stations) == 2

    def test_station_count_validator(self) -> None:
        with pytest.raises(ValueError, match="total_stations=3 but 1 station"):
            blank = ShapeDescription(overall_length=38.0, max_diameter=6.2)
            ProcessPlan(
                total_stations=3,
                blank_diameter=6.2,
                blank_length=38.0,
                stations=[
                    StationPlan(
                        station_number=1,
                        operation=OperationType.upsetting,
                        description="s1",
                        input_shape=blank,
                        output_shape=blank,
                    )
                ],
                confidence=ConfidenceLevel.high,
                reasoning_summary="test",
            )

    def test_upset_ratio_limit(self) -> None:
        blank = ShapeDescription(overall_length=38.0, max_diameter=6.2)
        with pytest.raises(ValueError, match="Upset ratio 2.5 exceeds"):
            StationPlan(
                station_number=1,
                operation=OperationType.upsetting,
                description="s1",
                input_shape=blank,
                output_shape=blank,
                upset_ratio=2.5,
            )

    def test_json_roundtrip(self, sample_process_plan: ProcessPlan) -> None:
        data = json.loads(sample_process_plan.model_dump_json())
        restored = ProcessPlan(**data)
        assert restored.total_stations == sample_process_plan.total_stations


class TestDieParameters:
    def test_instantiate(self, sample_die_params: list[DieParameters]) -> None:
        assert len(sample_die_params) == 2
        assert sample_die_params[0].station_number == 1

    def test_component_type_validator(self) -> None:
        with pytest.raises(ValueError, match="punch field must have component_type='punch'"):
            die = DieComponentParams(
                component_type="die",
                material="SKD11",
                hardness_hrc_min=60.0,
                hardness_hrc_max=62.0,
                geometry_type=DieGeometryType.cylindrical,
                outer_diameter=20.0,
                working_length=40.0,
            )
            DieParameters(station_number=1, punch=die, die=die, clearance_mm=0.1)

    def test_json_roundtrip(self, sample_die_params: list[DieParameters]) -> None:
        for dp in sample_die_params:
            data = json.loads(dp.model_dump_json())
            restored = DieParameters(**data)
            assert restored.station_number == dp.station_number


class TestVerificationResult:
    def test_passed_computed_from_checks(self) -> None:
        result = VerificationResult(
            passed=True,  # will be recomputed
            checks=[
                VerificationCheck(
                    check_name="volume_conservation",
                    passed=False,
                    severity=CheckSeverity.error,
                    message="Volume deviation exceeds 3%",
                )
            ],
        )
        # model_validator should set passed=False because error check failed
        assert result.passed is False

    def test_warnings_dont_fail(self) -> None:
        result = VerificationResult(
            passed=True,
            checks=[
                VerificationCheck(
                    check_name="expected_life",
                    passed=False,
                    severity=CheckSeverity.warning,
                    message="Expected life estimate unavailable",
                )
            ],
        )
        assert result.passed is True


class TestDesignResult:
    def test_instantiate(
        self,
        m6x33_flat_head: PartFeatures,
        sample_process_plan: ProcessPlan,
        sample_die_params: list[DieParameters],
    ) -> None:
        result = DesignResult(
            design_id="00000000-0000-0000-0000-000000000001",
            order_id="order-001",
            part_features=m6x33_flat_head,
            process_plan=sample_process_plan,
            die_parameters=sample_die_params,
            verification=VerificationResult(passed=True, checks=[]),
            confidence=ConfidenceLevel.high,
            status=DesignStatus.completed,
        )
        assert result.design_id == "00000000-0000-0000-0000-000000000001"

    def test_json_roundtrip(
        self,
        m6x33_flat_head: PartFeatures,
        sample_process_plan: ProcessPlan,
        sample_die_params: list[DieParameters],
    ) -> None:
        result = DesignResult(
            design_id="00000000-0000-0000-0000-000000000002",
            order_id="order-002",
            part_features=m6x33_flat_head,
            process_plan=sample_process_plan,
            die_parameters=sample_die_params,
            verification=VerificationResult(passed=True, checks=[]),
            confidence=ConfidenceLevel.medium,
        )
        data = json.loads(result.model_dump_json())
        restored = DesignResult(**data)
        assert restored.design_id == result.design_id
        assert restored.confidence == ConfidenceLevel.medium


class TestParsedDrawing:
    def test_instantiate(self) -> None:
        parsed = ParsedDrawing(
            file_path="s3://fastenergpt/orders/001/product_drawing.dxf",
            file_format="dxf",
            title_block=TitleBlock(
                part_number="18149-D6",
                title="M6×33 FLAT HEAD BOLT",
                material="10B21",
                scale="1:1",
            ),
            entity_count=142,
            parse_confidence=ConfidenceLevel.high,
        )
        assert parsed.title_block.part_number == "18149-D6"

    def test_dimension_extraction(self) -> None:
        from app.data.schemas import DimensionType
        dim = ExtractedDimension(
            dimension_type=DimensionType.diameter,
            value=6.0,
            label="⌀6.0",
            layer="DIMENSION",
        )
        assert dim.value == 6.0
