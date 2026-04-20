"""
Parametric 3D punch models using CADQuery.

Each template class takes DieComponentParams and generates a CADQuery solid
representing the punch geometry. Templates cover common punch types used in
cold-heading: flat-face, pre-form (profiled cavity), and finish punches.

All punches are generated as positive solids (the punch body), not cavities.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

from app.data.schemas import DieComponentParams, DieGeometryType


def _require_cadquery() -> None:
    if not CADQUERY_AVAILABLE:
        raise ImportError(
            "cadquery is not installed. Install with: pip install cadquery\n"
            "Or via conda: conda install -c cadquery cadquery"
        )


class PunchTemplateBase(ABC):
    """Abstract base for all parametric punch 3D models."""

    @abstractmethod
    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        """Generate a 3D CADQuery solid for this punch type."""


class FlatPunchTemplate(PunchTemplateBase):
    """
    Flat-bottom punch for upsetting operations.

    Geometry: cylindrical shank → shoulder transition → flat working face.
    Used for Station 1 pre-forming and simple upsetting.
    """

    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        _require_cadquery()

        wd = params.outer_diameter          # working diameter
        wl = params.working_length          # total length
        sd = params.shoulder_diameter or wd * 1.5
        shoulder_len = min(wl * 0.25, 25.0)
        working_len = wl - shoulder_len

        punch = (
            cq.Workplane("XY")
            # Working section (bottom)
            .cylinder(working_len, wd / 2)
            .faces(">Z")
            .workplane()
            # Shoulder (top)
            .cylinder(shoulder_len, sd / 2)
        )
        return punch


class PreformPunchTemplate(PunchTemplateBase):
    """
    Pre-forming punch with a simple cavity or stepped profile.

    Used for intermediate stations where the head is partially formed.
    Geometry: shank → shoulder → stepped working section.
    """

    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        _require_cadquery()

        wd = params.outer_diameter
        wl = params.working_length
        id_d = params.inner_diameter or wd * 0.4  # cavity / bore diameter
        cavity_depth = params.cavity_depth or wl * 0.3
        sd = params.shoulder_diameter or wd * 1.5
        shoulder_len = min(wl * 0.25, 20.0)
        body_len = wl - shoulder_len

        punch = (
            cq.Workplane("XY")
            .cylinder(body_len, wd / 2)
            .faces(">Z")
            .workplane()
            .cylinder(shoulder_len, sd / 2)
        )

        # Subtract cavity (blind bore in the working face)
        cavity = (
            cq.Workplane("XY")
            .cylinder(cavity_depth, id_d / 2)
        )
        punch = punch.cut(cavity)
        return punch


class FinishPunchTemplate(PunchTemplateBase):
    """
    Finishing punch with the final product head profile.

    For flat-head fasteners: creates the 90° countersink geometry.
    For hex-head bolts: creates the hexagonal pocket.
    """

    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        _require_cadquery()

        wd = params.outer_diameter
        wl = params.working_length
        angle = params.approach_angle_deg or 90.0
        land = params.land_length or 2.0
        sd = params.shoulder_diameter or wd * 1.5
        shoulder_len = min(wl * 0.25, 20.0)
        body_len = wl - shoulder_len

        # Conical cavity for flat-head (countersink)
        half_angle = (180.0 - angle) / 2.0
        cone_height = (wd / 2) / math.tan(math.radians(half_angle)) if half_angle > 0 else wd * 0.5
        cone_height = min(cone_height, body_len * 0.6)

        punch = (
            cq.Workplane("XY")
            .cylinder(body_len, wd / 2)
            .faces(">Z")
            .workplane()
            .cylinder(shoulder_len, sd / 2)
        )

        # Countersink cavity
        cone_profile = (
            cq.Workplane("XY")
            .add(
                cq.CQ(
                    cq.Solid.makeCone(wd / 2, land / 2, cone_height)
                )
            )
        )
        punch = punch.cut(cone_profile)
        return punch


# ---------------------------------------------------------------------------
# Template factory
# ---------------------------------------------------------------------------

_TEMPLATE_MAP: dict[DieGeometryType, type[PunchTemplateBase]] = {
    DieGeometryType.flat_face: FlatPunchTemplate,
    DieGeometryType.stepped: PreformPunchTemplate,
    DieGeometryType.conical: FinishPunchTemplate,
    DieGeometryType.closed_heading: FinishPunchTemplate,
    DieGeometryType.open_heading: FlatPunchTemplate,
}


def build_punch(params: DieComponentParams) -> "cq.Workplane":
    """
    Select and execute the appropriate punch template for the given parameters.

    Falls back to FlatPunchTemplate if the geometry type is not mapped.
    """
    _require_cadquery()
    template_cls = _TEMPLATE_MAP.get(params.geometry_type, FlatPunchTemplate)
    return template_cls().generate(params)
