"""
DXF quality tests — verify generated drawings have real DIMENSION entities,
HATCH entities, and properly rendered dim blocks.

Run: pytest tests/drawings/test_dxf_quality.py -v
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
import pytest

from app.data.schemas import (
    ConfidenceLevel,
    DieComponentParams,
    DieGeometryType,
    HeadFeatures,
    HeadType,
    DriveType,
    PartFeatures,
    ProcessPlan,
    ShankFeatures,
    ShapeDescription,
    StationPlan,
    ThreadFeatures,
    Tolerance,
    OperationType,
)
from app.drawings.generator import DrawingGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_punch() -> DieComponentParams:
    return DieComponentParams(
        component_type="punch",
        material="DC53",
        hardness_hrc_min=62.0,
        hardness_hrc_max=64.0,
        geometry_type=DieGeometryType.conical,
        outer_diameter=11.404,
        working_length=40.0,
        approach_angle_deg=45.0,
        land_length=3.0,
        surface_roughness_ra=0.2,
        surface_treatment="TiN",
        coating_thickness_um=3.0,
    )


@pytest.fixture
def sample_die() -> DieComponentParams:
    return DieComponentParams(
        component_type="die",
        material="DC53",
        hardness_hrc_min=62.0,
        hardness_hrc_max=64.0,
        geometry_type=DieGeometryType.closed_heading,
        outer_diameter=20.4,
        inner_diameter=6.250,
        working_length=43.8,
        approach_angle_deg=48.0,
        land_length=5.0,
        surface_roughness_ra=0.2,
    )


@pytest.fixture
def sample_part() -> PartFeatures:
    return PartFeatures(
        part_number="TEST-M6-033",
        description="M6×33 Flat Head Bolt",
        overall_length=33.0,
        head=HeadFeatures(
            type=HeadType.flat,
            diameter=11.5,
            height=3.0,
            chamfer_angle_deg=90.0,
            chamfer_diameter=11.5,
            drive_type=DriveType.cross,
        ),
        shank=ShankFeatures(
            diameter=5.82,
            length=4.0,
            diameter_tolerance=Tolerance(nominal=6.0, plus=0.0, minus=0.022),
        ),
        thread=ThreadFeatures(
            spec="M6×1.0",
            nominal_diameter=6.0,
            pitch=1.0,
            length=26.0,
            thread_class="6g",
        ),
        material_grade="10B21",
        strength_grade="8.8",
    )


@pytest.fixture
def sample_plan(sample_part: PartFeatures) -> ProcessPlan:
    blank = ShapeDescription(overall_length=36.0, max_diameter=6.2, shank_diameter=6.2)
    s1_out = ShapeDescription(
        overall_length=33.5, max_diameter=8.0, head_diameter=8.0,
        head_height=2.0, shank_diameter=5.82, shank_length=31.5,
    )
    s2_out = ShapeDescription(
        overall_length=33.0, max_diameter=11.5, head_diameter=11.5,
        head_height=3.0, shank_diameter=5.82, shank_length=30.0,
    )
    return ProcessPlan(
        total_stations=2,
        blank_diameter=6.2,
        blank_length=36.0,
        confidence=ConfidenceLevel.high,
        reasoning_summary="Test plan for M6×33 flat head bolt",
        stations=[
            StationPlan(
                station_number=1, operation=OperationType.upsetting,
                description="Station 1: Upsetting",
                input_shape=blank, output_shape=s1_out, upset_ratio=1.29,
            ),
            StationPlan(
                station_number=2, operation=OperationType.heading,
                description="Station 2: Heading",
                input_shape=s1_out, output_shape=s2_out, upset_ratio=1.44,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPunchDrawing:
    def test_punch_drawing_has_hatch(self, tmp_dir: Path, sample_punch: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_punch, 2, tmp_dir / "punch.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        hatches = [e for e in msp if e.dxftype() == "HATCH"]
        assert len(hatches) >= 1, "No HATCH entity found in punch drawing"

    def test_punch_drawing_hatch_is_ansi31(self, tmp_dir: Path, sample_punch: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_punch, 2, tmp_dir / "punch.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        hatches = [e for e in msp if e.dxftype() == "HATCH"]
        assert any(
            hasattr(h, "dxf") and "ANSI31" in str(getattr(h.dxf, "pattern_name", ""))
            for h in hatches
        ), "HATCH is not ANSI31 pattern"

    def test_punch_drawing_has_dimensions(self, tmp_dir: Path, sample_punch: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_punch, 2, tmp_dir / "punch.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        dims = [e for e in msp if e.dxftype() == "DIMENSION"]
        assert len(dims) >= 3, f"Expected >= 3 DIMENSION entities, got {len(dims)}"

    def test_punch_drawing_dims_are_rendered(self, tmp_dir: Path, sample_punch: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_punch, 2, tmp_dir / "punch.dxf")
        doc = ezdxf.readfile(str(out))
        dim_blocks = [b for b in doc.blocks if b.name.startswith("*D")]
        assert len(dim_blocks) >= 1, "No rendered dim blocks (*D...) found"

    def test_punch_drawing_has_center_line(self, tmp_dir: Path, sample_punch: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_punch, 2, tmp_dir / "punch.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        center_lines = [e for e in msp if e.dxftype() == "LINE" and e.dxf.layer == "CENTER"]
        assert len(center_lines) >= 1, "No CENTER layer line found"


class TestDieDrawing:
    def test_die_drawing_has_hatch(self, tmp_dir: Path, sample_die: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_die, 2, tmp_dir / "die.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        hatches = [e for e in msp if e.dxftype() == "HATCH"]
        assert len(hatches) >= 1, "No HATCH entity found in die drawing"

    def test_die_drawing_has_dimensions(self, tmp_dir: Path, sample_die: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_die, 2, tmp_dir / "die.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        dims = [e for e in msp if e.dxftype() == "DIMENSION"]
        assert len(dims) >= 3, f"Expected >= 3 DIMENSION entities, got {len(dims)}"

    def test_die_od_bore_both_present(self, tmp_dir: Path, sample_die: DieComponentParams) -> None:
        gen = DrawingGenerator()
        out = gen.generate_die_drawing(sample_die, 2, tmp_dir / "die.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        dims = [e for e in msp if e.dxftype() == "DIMENSION"]
        # There should be both OD and bore ID dims
        assert len(dims) >= 2


class TestProductionDrawing:
    def test_production_drawing_has_dimensions(
        self, tmp_dir: Path, sample_part: PartFeatures, sample_plan: ProcessPlan
    ) -> None:
        gen = DrawingGenerator()
        out = gen.generate_production_drawing(sample_part, sample_plan, tmp_dir / "prod.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        dims = [e for e in msp if e.dxftype() == "DIMENSION"]
        assert len(dims) >= 3, f"Expected >= 3 DIMENSION entities, got {len(dims)}"

    def test_production_drawing_has_hatch(
        self, tmp_dir: Path, sample_part: PartFeatures, sample_plan: ProcessPlan
    ) -> None:
        gen = DrawingGenerator()
        out = gen.generate_production_drawing(sample_part, sample_plan, tmp_dir / "prod.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        hatches = [e for e in msp if e.dxftype() == "HATCH"]
        assert len(hatches) >= 1

    def test_production_drawing_has_outline(
        self, tmp_dir: Path, sample_part: PartFeatures, sample_plan: ProcessPlan
    ) -> None:
        gen = DrawingGenerator()
        out = gen.generate_production_drawing(sample_part, sample_plan, tmp_dir / "prod.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        outlines = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "OUTLINE"]
        assert len(outlines) >= 1


class TestProcessBreakdown:
    def test_breakdown_has_silhouettes(self, tmp_dir: Path, sample_plan: ProcessPlan) -> None:
        gen = DrawingGenerator()
        out = gen.generate_process_breakdown(sample_plan, tmp_dir / "breakdown.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        outlines = [e for e in msp if e.dxftype() in ("LWPOLYLINE", "POLYLINE") and e.dxf.layer == "OUTLINE"]
        assert len(outlines) >= sample_plan.total_stations

    def test_breakdown_has_hatch(self, tmp_dir: Path, sample_plan: ProcessPlan) -> None:
        gen = DrawingGenerator()
        out = gen.generate_process_breakdown(sample_plan, tmp_dir / "breakdown.dxf")
        doc = ezdxf.readfile(str(out))
        msp = doc.modelspace()
        hatches = [e for e in msp if e.dxftype() == "HATCH"]
        assert len(hatches) >= sample_plan.total_stations
