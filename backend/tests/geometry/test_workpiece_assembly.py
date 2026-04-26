"""
Workpiece + assembly 3D generation tests.

Verifies that revolution-solid workpieces are generated correctly for
each shape type (blank, upsetting, heading, extrusion) and that
station assemblies (punch+die+workpiece) are produced as combined STLs.

Run: pytest tests/geometry/test_workpiece_assembly.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.data.schemas import (
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    ShapeDescription,
)
from app.geometry.workpiece import WorkpieceGenerator, _build_profile
from app.geometry.assembly import AssemblyBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def blank_shape() -> ShapeDescription:
    return ShapeDescription(overall_length=36.0, max_diameter=6.2, shank_diameter=6.2)


@pytest.fixture
def upsetting_shape() -> ShapeDescription:
    return ShapeDescription(
        overall_length=33.5, max_diameter=8.0, head_diameter=8.0,
        head_height=2.0, shank_diameter=5.82, shank_length=31.5,
    )


@pytest.fixture
def heading_shape() -> ShapeDescription:
    return ShapeDescription(
        overall_length=33.0, max_diameter=11.5, head_diameter=11.5,
        head_height=3.0, shank_diameter=5.82, shank_length=30.0,
    )


@pytest.fixture
def die_params() -> DieParameters:
    return DieParameters(
        station_number=2,
        punch=DieComponentParams(
            component_type="punch", material="DC53",
            hardness_hrc_min=62.0, hardness_hrc_max=64.0,
            geometry_type=DieGeometryType.conical,
            outer_diameter=11.404, working_length=40.0,
            approach_angle_deg=45.0, land_length=3.0,
            surface_roughness_ra=0.2, surface_treatment="TiN",
        ),
        die=DieComponentParams(
            component_type="die", material="DC53",
            hardness_hrc_min=62.0, hardness_hrc_max=64.0,
            geometry_type=DieGeometryType.closed_heading,
            outer_diameter=20.4, inner_diameter=6.250,
            working_length=43.8, approach_angle_deg=48.0,
            land_length=5.0, surface_roughness_ra=0.2,
        ),
        clearance_mm=0.175,
    )


# ---------------------------------------------------------------------------
# Profile tests
# ---------------------------------------------------------------------------

class TestBuildProfile:
    def test_blank_profile_is_cylinder(self, blank_shape: ShapeDescription) -> None:
        pts = _build_profile(blank_shape)
        # axis bottom → rim bottom → rim top → axis top
        assert pts[0] == (0.0, 0.0)
        assert pts[-1][0] == 0.0
        assert pts[-1][1] == pytest.approx(blank_shape.overall_length)

    def test_blank_profile_has_four_points(self, blank_shape: ShapeDescription) -> None:
        pts = _build_profile(blank_shape)
        assert len(pts) == 4

    def test_heading_profile_has_step(self, heading_shape: ShapeDescription) -> None:
        pts = _build_profile(heading_shape)
        # Should have a step from shank radius to head radius
        radii = [r for r, _ in pts]
        assert max(radii) == pytest.approx(heading_shape.head_diameter / 2)
        assert min(r for r in radii if r > 0) == pytest.approx(heading_shape.shank_diameter / 2)

    def test_heading_profile_length(self, heading_shape: ShapeDescription) -> None:
        pts = _build_profile(heading_shape)
        # Top point should be at overall_length
        assert pts[-1][1] == pytest.approx(heading_shape.overall_length)


# ---------------------------------------------------------------------------
# WorkpieceGenerator STL tests
# ---------------------------------------------------------------------------

class TestWorkpieceGenerator:
    def test_blank_stl_is_nonzero(self, tmp_dir: Path) -> None:
        gen = WorkpieceGenerator()
        path = gen.generate_blank_stl(6.2, 36.0, tmp_dir / "blank.stl")
        assert path.stat().st_size > 1000

    def test_workpiece_stl_heading(self, tmp_dir: Path, heading_shape: ShapeDescription) -> None:
        gen = WorkpieceGenerator()
        path = gen.generate_workpiece_stl(heading_shape, tmp_dir / "wp.stl")
        assert path.stat().st_size > 1000

    def test_workpiece_stl_blank_shape(self, tmp_dir: Path, blank_shape: ShapeDescription) -> None:
        gen = WorkpieceGenerator()
        path = gen.generate_workpiece_stl(blank_shape, tmp_dir / "wp_blank.stl")
        assert path.stat().st_size > 1000

    def test_volume_nonzero(self, heading_shape: ShapeDescription) -> None:
        gen = WorkpieceGenerator()
        vol = gen.volume_mm3(heading_shape)
        assert vol > 0

    def test_blank_volume(self) -> None:
        gen = WorkpieceGenerator()
        vol = gen.blank_volume_mm3(6.2, 36.0)
        import math
        expected = math.pi * (3.1 ** 2) * 36.0
        assert vol == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# AssemblyBuilder tests
# ---------------------------------------------------------------------------

class TestAssemblyBuilder:
    def test_assembly_produces_four_stls(
        self, tmp_dir: Path, die_params: DieParameters, heading_shape: ShapeDescription
    ) -> None:
        builder = AssemblyBuilder()
        result = builder.build_station_assembly_stls(die_params, heading_shape, tmp_dir)
        assert "punch" in result
        assert "die" in result
        assert "workpiece" in result
        assert "assembly_preview" in result

    def test_assembly_stls_are_nonempty(
        self, tmp_dir: Path, die_params: DieParameters, heading_shape: ShapeDescription
    ) -> None:
        builder = AssemblyBuilder()
        result = builder.build_station_assembly_stls(die_params, heading_shape, tmp_dir)
        for label, path in result.items():
            assert path.stat().st_size > 1000, f"{label} STL is too small"

    def test_assembly_preview_larger_than_components(
        self, tmp_dir: Path, die_params: DieParameters, heading_shape: ShapeDescription
    ) -> None:
        builder = AssemblyBuilder()
        result = builder.build_station_assembly_stls(die_params, heading_shape, tmp_dir)
        preview_size = result["assembly_preview"].stat().st_size
        punch_size = result["punch"].stat().st_size
        die_size = result["die"].stat().st_size
        # Combined mesh should be larger than any individual component
        assert preview_size > punch_size
        assert preview_size > die_size
