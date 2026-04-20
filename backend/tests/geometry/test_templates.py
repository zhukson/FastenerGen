"""Tests for 3D parametric punch and die templates."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.data.schemas import DieComponentParams, DieGeometryType


@pytest.fixture
def punch_params() -> DieComponentParams:
    return DieComponentParams(
        component_type="punch",
        material="SKD11",
        hardness_hrc_min=60.0,
        hardness_hrc_max=62.0,
        geometry_type=DieGeometryType.flat_face,
        outer_diameter=20.0,
        working_length=40.0,
        surface_roughness_ra=0.4,
    )


@pytest.fixture
def die_params() -> DieComponentParams:
    return DieComponentParams(
        component_type="die",
        material="SKD11",
        hardness_hrc_min=60.0,
        hardness_hrc_max=62.0,
        geometry_type=DieGeometryType.cylindrical,
        outer_diameter=40.0,
        inner_diameter=6.2,
        working_length=35.0,
        surface_roughness_ra=0.2,
    )


class TestPunchTemplates:
    def test_flat_punch_generates_solid(self, punch_params: DieComponentParams) -> None:
        from app.geometry.punch_templates import FlatPunchTemplate

        template = FlatPunchTemplate()
        shape = template.generate(punch_params)
        assert shape is not None
        # CADQuery solid should have non-zero volume
        vol = shape.val().Volume()
        assert vol > 0

    def test_build_punch_factory(self, punch_params: DieComponentParams) -> None:
        from app.geometry.punch_templates import build_punch

        shape = build_punch(punch_params)
        assert shape.val().Volume() > 0

    def test_conical_punch(self) -> None:
        from app.geometry.punch_templates import FinishPunchTemplate

        params = DieComponentParams(
            component_type="punch",
            material="DC53",
            hardness_hrc_min=62.0,
            hardness_hrc_max=64.0,
            geometry_type=DieGeometryType.conical,
            outer_diameter=18.0,
            working_length=42.0,
            approach_angle_deg=90.0,
            surface_roughness_ra=0.2,
        )
        shape = FinishPunchTemplate().generate(params)
        assert shape.val().Volume() > 0


class TestDieTemplates:
    def test_straight_die_generates_solid(self, die_params: DieComponentParams) -> None:
        from app.geometry.die_templates import StraightDieTemplate

        template = StraightDieTemplate()
        shape = template.generate(die_params)
        vol = shape.val().Volume()
        assert vol > 0

    def test_build_die_factory(self, die_params: DieComponentParams) -> None:
        from app.geometry.die_templates import build_die

        shape = build_die(die_params)
        assert shape.val().Volume() > 0

    def test_tapered_die(self) -> None:
        from app.geometry.die_templates import TaperedDieTemplate

        params = DieComponentParams(
            component_type="die",
            material="SKD11",
            hardness_hrc_min=60.0,
            hardness_hrc_max=62.0,
            geometry_type=DieGeometryType.conical,
            outer_diameter=40.0,
            inner_diameter=5.5,
            working_length=30.0,
            approach_angle_deg=12.0,
            land_length=4.0,
        )
        shape = TaperedDieTemplate().generate(params)
        assert shape.val().Volume() > 0

    def test_forming_die(self) -> None:
        from app.geometry.die_templates import FormingDieTemplate

        params = DieComponentParams(
            component_type="die",
            material="DC53",
            hardness_hrc_min=62.0,
            hardness_hrc_max=64.0,
            geometry_type=DieGeometryType.closed_heading,
            outer_diameter=40.0,
            inner_diameter=6.1,
            working_length=32.0,
            cavity_depth=4.5,
            approach_angle_deg=90.0,
        )
        shape = FormingDieTemplate().generate(params)
        assert shape.val().Volume() > 0


class TestExporter:
    def test_export_step(self, punch_params: DieComponentParams) -> None:
        from app.geometry.punch_templates import build_punch
        from app.geometry.exporter import GeometryExporter

        shape = build_punch(punch_params)
        exporter = GeometryExporter()
        with tempfile.TemporaryDirectory() as tmp:
            path = exporter.to_step(shape, Path(tmp) / "punch.step")
            assert path.exists()
            assert path.stat().st_size > 1000  # STEP files are always several KB

    def test_export_stl(self, punch_params: DieComponentParams) -> None:
        from app.geometry.punch_templates import build_punch
        from app.geometry.exporter import GeometryExporter

        shape = build_punch(punch_params)
        exporter = GeometryExporter()
        with tempfile.TemporaryDirectory() as tmp:
            path = exporter.to_stl(shape, Path(tmp) / "punch.stl")
            assert path.exists()
            assert path.stat().st_size > 100

    def test_export_die_stl(self, die_params: DieComponentParams) -> None:
        from app.geometry.die_templates import build_die
        from app.geometry.exporter import GeometryExporter

        shape = build_die(die_params)
        exporter = GeometryExporter()
        with tempfile.TemporaryDirectory() as tmp:
            path = exporter.to_stl(shape, Path(tmp) / "die.stl")
            assert path.exists()
            assert path.stat().st_size > 100
