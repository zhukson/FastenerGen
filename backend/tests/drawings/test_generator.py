"""Tests for the DXF drawing generator."""

from __future__ import annotations

import tempfile
from pathlib import Path

import ezdxf
import pytest

from app.data.schemas import (
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    HeadFeatures,
    HeadType,
    PartFeatures,
    ProcessPlan,
    ShankFeatures,
    ShapeDescription,
    StationPlan,
    OperationType,
    ConfidenceLevel,
    ThreadFeatures,
)
from app.drawings.generator import DrawingGenerator


@pytest.fixture
def punch_params() -> DieComponentParams:
    return DieComponentParams(
        component_type="punch",
        material="SKD11",
        hardness_hrc_min=60.0,
        hardness_hrc_max=62.0,
        geometry_type=DieGeometryType.conical,
        outer_diameter=20.0,
        working_length=45.0,
        approach_angle_deg=90.0,
        surface_roughness_ra=0.2,
        surface_treatment="TiN",
        coating_thickness_um=3.0,
    )


@pytest.fixture
def die_params(punch_params: DieComponentParams) -> DieParameters:
    die = DieComponentParams(
        component_type="die",
        material="SKD11",
        hardness_hrc_min=60.0,
        hardness_hrc_max=62.0,
        geometry_type=DieGeometryType.closed_heading,
        outer_diameter=40.0,
        inner_diameter=6.1,
        working_length=32.0,
        cavity_depth=4.2,
        approach_angle_deg=90.0,
        surface_roughness_ra=0.2,
        surface_treatment="TiCN",
        coating_thickness_um=3.0,
    )
    return DieParameters(station_number=1, punch=punch_params, die=die, clearance_mm=0.05)


@pytest.fixture
def part_features() -> PartFeatures:
    return PartFeatures(
        part_number="TEST-001",
        description="M6×33 Test Bolt",
        overall_length=33.0,
        head=HeadFeatures(type=HeadType.flat, diameter=12.0, height=3.6),
        shank=ShankFeatures(diameter=6.0, length=8.0),
        thread=ThreadFeatures(
            spec="M6×1.0", nominal_diameter=6.0, pitch=1.0, length=20.0, thread_class="6g"
        ),
        material_grade="10B21",
        strength_grade="8.8",
    )


@pytest.fixture
def process_plan() -> ProcessPlan:
    blank = ShapeDescription(overall_length=38.0, max_diameter=6.2)
    out1 = ShapeDescription(overall_length=35.0, max_diameter=8.0, head_diameter=8.0, head_height=2.0)
    out2 = ShapeDescription(overall_length=33.5, max_diameter=12.0, head_diameter=12.0, head_height=3.6)
    return ProcessPlan(
        total_stations=2,
        blank_diameter=6.2,
        blank_length=38.0,
        stations=[
            StationPlan(station_number=1, operation=OperationType.upsetting, description="s1",
                        input_shape=blank, output_shape=out1, upset_ratio=1.29),
            StationPlan(station_number=2, operation=OperationType.heading, description="s2",
                        input_shape=out1, output_shape=out2, upset_ratio=1.5),
        ],
        confidence=ConfidenceLevel.high,
        reasoning_summary="test plan",
    )


class TestDrawingGenerator:
    def test_generate_die_drawing_creates_file(self, die_params: DieParameters) -> None:
        gen = DrawingGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "punch.dxf"
            result = gen.generate_die_drawing(die_params.punch, station_number=1, output_path=out)
            assert result.exists()
            assert result.stat().st_size > 0

    def test_generated_dxf_is_valid(self, die_params: DieParameters) -> None:
        gen = DrawingGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "die.dxf"
            gen.generate_die_drawing(die_params.die, station_number=1, output_path=out)
            # Should open without error
            doc = ezdxf.readfile(str(out))
            assert "TITLEBLOCK" in [layer.dxf.name for layer in doc.layers]

    def test_generated_dxf_has_outline_layer(self, die_params: DieParameters) -> None:
        gen = DrawingGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "punch.dxf"
            gen.generate_die_drawing(die_params.punch, station_number=1, output_path=out)
            doc = ezdxf.readfile(str(out))
            layer_names = [layer.dxf.name for layer in doc.layers]
            assert "OUTLINE" in layer_names

    def test_generate_production_drawing(self, part_features: PartFeatures, process_plan: ProcessPlan) -> None:
        gen = DrawingGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "production.dxf"
            result = gen.generate_production_drawing(part_features, process_plan, out)
            assert result.exists()
            assert result.stat().st_size > 0

    def test_generate_process_breakdown(self, process_plan: ProcessPlan) -> None:
        gen = DrawingGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "breakdown.dxf"
            result = gen.generate_process_breakdown(process_plan, out)
            assert result.exists()
            doc = ezdxf.readfile(str(out))
            assert doc is not None
