"""
Intermediate workpiece shape generation using CADQuery.

Generates 3D solids of the workpiece (billet) at each forming station,
from blank wire stock through to near-finished part. Each shape is a
revolution solid approximated from the ShapeDescription parameters.
Used for assembly preview and volume conservation verification.
"""

from __future__ import annotations

import math

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

from app.data.schemas import ShapeDescription, StationPlan


def _require_cadquery() -> None:
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery is not installed.")


class WorkpieceGenerator:
    """Generate 3D solids of intermediate workpiece shapes at each forming station."""

    def generate_blank(self, diameter: float, length: float) -> "cq.Workplane":
        """
        Generate the initial wire blank (cylinder).

        Args:
            diameter: Wire stock diameter in mm.
            length: Cut length in mm.
        """
        _require_cadquery()
        return cq.Workplane("XY").cylinder(length, diameter / 2)

    def generate_intermediate(self, shape: ShapeDescription) -> "cq.Workplane":
        """
        Generate workpiece geometry for an intermediate forming station.

        Approximates the workpiece as a stepped revolution solid:
        - Shank section: cylinder of shank_diameter × shank_length
        - Head section: cylinder of head_diameter × head_height (if present)
        """
        _require_cadquery()

        shank_d = shape.shank_diameter or shape.max_diameter
        shank_l = shape.shank_length or (shape.overall_length * 0.8)
        head_d = shape.head_diameter
        head_h = shape.head_height

        # Start with shank cylinder
        wp = cq.Workplane("XY").cylinder(shank_l, shank_d / 2)

        if head_d and head_h and head_d > shank_d:
            # Stack head on top of shank
            wp = (
                wp.faces(">Z")
                .workplane()
                .cylinder(head_h, head_d / 2)
            )

        return wp

    def generate_finished(self, shape: ShapeDescription) -> "cq.Workplane":
        """Generate near-finished part shape after the final forming station."""
        _require_cadquery()
        return self.generate_intermediate(shape)

    def volume_mm3(self, shape: ShapeDescription) -> float:
        """
        Estimate workpiece volume (mm³) analytically from ShapeDescription.

        Used for volume conservation verification without needing CADQuery.
        """
        shank_d = shape.shank_diameter or shape.max_diameter
        shank_l = shape.shank_length or shape.overall_length
        vol = math.pi * (shank_d / 2) ** 2 * shank_l

        if shape.head_diameter and shape.head_height and shape.head_diameter > shank_d:
            vol += math.pi * (shape.head_diameter / 2) ** 2 * shape.head_height

        if shape.extrusion_diameter and shape.extrusion_length:
            vol += math.pi * (shape.extrusion_diameter / 2) ** 2 * shape.extrusion_length

        return vol

    def blank_volume_mm3(self, diameter: float, length: float) -> float:
        """Volume of cylindrical wire blank in mm³."""
        return math.pi * (diameter / 2) ** 2 * length
