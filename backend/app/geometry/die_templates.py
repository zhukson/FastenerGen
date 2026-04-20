"""
Parametric 3D die (cavity insert) models using CADQuery.

Each template generates the die body as a solid with a cavity cut out.
Templates: straight bore, tapered (extrusion), forming (head cavity).
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
        raise ImportError("cadquery is not installed.")


class DieTemplateBase(ABC):
    """Abstract base for all parametric die 3D models."""

    @abstractmethod
    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        """Generate 3D CADQuery solid for this die type."""


class StraightDieTemplate(DieTemplateBase):
    """
    Straight cylindrical bore die for upsetting stations.

    Geometry: solid cylinder with a straight bore through the center.
    The workpiece slides into the bore; the punch enters from the top.
    """

    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        _require_cadquery()

        od = params.outer_diameter
        id_d = params.inner_diameter or od * 0.3
        length = params.working_length
        entry_r = params.entry_radius or 0.5

        # Solid cylinder
        body = cq.Workplane("XY").cylinder(length, od / 2)

        # Bore through center
        bore = cq.Workplane("XY").cylinder(length, id_d / 2)
        die = body.cut(bore)

        return die


class TaperedDieTemplate(DieTemplateBase):
    """
    Tapered bore die for forward extrusion and reduction stations.

    Geometry: outer cylinder with tapered bore (entry > exit).
    The approach angle reduces material diameter.
    """

    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        _require_cadquery()

        od = params.outer_diameter
        id_exit = params.inner_diameter or od * 0.25
        length = params.working_length
        approach_angle = params.approach_angle_deg or 12.0  # degrees
        land = params.land_length or id_exit * 2.0
        relief_angle = params.relief_angle_deg or 5.0

        # Entry diameter (larger than exit)
        half_approach = math.radians(approach_angle / 2)
        id_entry = id_exit + 2 * (length - land) * math.tan(half_approach)
        id_entry = min(id_entry, od * 0.8)

        # Body
        body = cq.Workplane("XY").cylinder(length, od / 2)

        # Bore: cone (approach) + cylinder (land) + relief cone
        approach_h = (id_entry - id_exit) / (2 * math.tan(half_approach)) if half_approach > 0 else length * 0.6
        approach_h = min(approach_h, length - land)

        # Approach cone (top entry to land)
        cone_approach = cq.Workplane("XZ").add(
            cq.Solid.makeCone(id_entry / 2, id_exit / 2, approach_h)
        ).translate((0, 0, land))

        # Land cylinder
        land_bore = cq.Workplane("XY").cylinder(land, id_exit / 2)

        die = body.cut(cone_approach).cut(land_bore)
        return die


class FormingDieTemplate(DieTemplateBase):
    """
    Forming die with profiled cavity for head forming stations.

    Geometry: outer cylinder with a forming cavity at the top.
    Used in heading stations where the fastener head is formed.
    """

    def generate(self, params: DieComponentParams) -> "cq.Workplane":
        _require_cadquery()

        od = params.outer_diameter
        id_bore = params.inner_diameter or od * 0.25
        length = params.working_length
        cavity_depth = params.cavity_depth or od * 0.35
        approach_angle = params.approach_angle_deg or 90.0

        # Body
        body = cq.Workplane("XY").cylinder(length, od / 2)

        # Through bore (shank passes through)
        bore = cq.Workplane("XY").cylinder(length - cavity_depth, id_bore / 2)
        die = body.cut(bore)

        # Head-forming cavity (top)
        if approach_angle >= 85.0:
            # Cylindrical cavity (for flat/button head)
            cavity_r = od * 0.35
            cavity = (
                cq.Workplane("XY")
                .workplane(offset=length - cavity_depth)
                .cylinder(cavity_depth, cavity_r)
            )
        else:
            # Conical cavity (for oval/countersunk head)
            half_a = math.radians((180 - approach_angle) / 2)
            cone_r_top = id_bore / 2 + cavity_depth * math.tan(half_a)
            cone_r_top = min(cone_r_top, od * 0.45)
            cavity = cq.Workplane("XY").add(
                cq.Solid.makeCone(cone_r_top, id_bore / 2, cavity_depth)
            ).translate((0, 0, length - cavity_depth))

        die = die.cut(cavity)
        return die


# ---------------------------------------------------------------------------
# Template factory
# ---------------------------------------------------------------------------

_TEMPLATE_MAP: dict[DieGeometryType, type[DieTemplateBase]] = {
    DieGeometryType.cylindrical: StraightDieTemplate,
    DieGeometryType.stepped: StraightDieTemplate,
    DieGeometryType.conical: TaperedDieTemplate,
    DieGeometryType.open_heading: StraightDieTemplate,
    DieGeometryType.closed_heading: FormingDieTemplate,
    DieGeometryType.flat_face: FormingDieTemplate,
    DieGeometryType.trimming: StraightDieTemplate,
}


def build_die(params: DieComponentParams) -> "cq.Workplane":
    """Select and execute the appropriate die template for the given parameters."""
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery is not installed.")
    template_cls = _TEMPLATE_MAP.get(params.geometry_type, StraightDieTemplate)
    return template_cls().generate(params)
