"""
Intermediate workpiece shape generation.

Generates 3D revolution solids of the workpiece (billet) at each forming
station, from blank wire stock through to near-finished part.

Primary path: CADQuery (if available). For STL preview export, uses the
numpy+trimesh revolution-solid path (always available, no X11 required).

Profile convention:
  Z=0 = shank/tail end (bottom), Z=overall_length = head end (top).
  Profile is [(r, z), ...] with first/last point on r=0 for closed caps.
"""

from __future__ import annotations

import math
from pathlib import Path

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

from app.data.schemas import ShapeDescription


def _build_profile(shape: ShapeDescription) -> list[tuple[float, float]]:
    """
    Build a 2D radial profile for revolving around the Z axis.

    Handles four shape classes derived from ShapeDescription fields:
    - Blank / cylinder: no head_diameter set
    - Upsetting: head_diameter slightly > shank_diameter (partial upset)
    - Heading: head_diameter >> shank_diameter (formed head)
    - Extrusion: extrusion_diameter + extrusion_length (reduced tip)
    """
    L = shape.overall_length
    shank_r = (shape.shank_diameter or shape.max_diameter) / 2
    head_r = (shape.head_diameter / 2) if shape.head_diameter else shank_r
    head_h = shape.head_height or 0.0
    ext_d = shape.extrusion_diameter
    ext_l = shape.extrusion_length or 0.0

    pts: list[tuple[float, float]] = [(0.0, 0.0)]  # axis at bottom

    if ext_d and ext_l > 0.1:
        ext_r = ext_d / 2
        pts += [
            (ext_r, 0.0),
            (ext_r, ext_l),
            (shank_r, ext_l),
        ]
    else:
        pts.append((shank_r, 0.0))

    if head_r > shank_r * 1.05 and head_h > 0.1:
        shank_end = max(0.1, L - head_h)
        pts += [
            (shank_r, shank_end),
            (head_r, shank_end),
            (head_r, L),
        ]
    else:
        pts.append((shank_r, L))

    pts.append((0.0, L))  # axis at top
    return pts


class WorkpieceGenerator:
    """Generate 3D solids of intermediate workpiece shapes at each forming station."""

    # ------------------------------------------------------------------
    # STL export (trimesh path — no CADQuery required)
    # ------------------------------------------------------------------

    def generate_workpiece_stl(self, shape: ShapeDescription, path: Path) -> Path:
        """
        Export a workpiece revolution solid as STL.

        Works without CADQuery — uses numpy+trimesh _revolve_profile.
        Used for web 3D preview (Three.js).
        """
        from app.geometry.numpy_templates import _revolve_profile, export_stl

        profile = _build_profile(shape)
        mesh = _revolve_profile(profile, sections=48)
        return export_stl(mesh, path)

    def generate_blank_stl(self, diameter: float, length: float, path: Path) -> Path:
        """Export the initial cylindrical wire blank as STL."""
        from app.geometry.numpy_templates import _revolve_profile, export_stl

        r = diameter / 2
        profile: list[tuple[float, float]] = [
            (0.0, 0.0),
            (r, 0.0),
            (r, length),
            (0.0, length),
        ]
        mesh = _revolve_profile(profile, sections=48)
        return export_stl(mesh, path)

    # ------------------------------------------------------------------
    # CADQuery path (kept for STEP export when CQ is available)
    # ------------------------------------------------------------------

    def generate_blank(self, diameter: float, length: float) -> "cq.Workplane":
        """Generate the initial wire blank (cylinder) as a CQ solid."""
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is not installed.")
        return cq.Workplane("XY").cylinder(length, diameter / 2)

    def generate_intermediate(self, shape: ShapeDescription) -> "cq.Workplane":
        """Generate workpiece CQ solid for an intermediate forming station."""
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is not installed.")

        shank_d = shape.shank_diameter or shape.max_diameter
        shank_l = shape.shank_length or (shape.overall_length * 0.8)
        head_d = shape.head_diameter
        head_h = shape.head_height

        wp = cq.Workplane("XY").cylinder(shank_l, shank_d / 2)

        if head_d and head_h and head_d > shank_d:
            wp = wp.faces(">Z").workplane().cylinder(head_h, head_d / 2)

        return wp

    def generate_finished(self, shape: ShapeDescription) -> "cq.Workplane":
        """Generate near-finished part shape after the final forming station."""
        return self.generate_intermediate(shape)

    # ------------------------------------------------------------------
    # Volume helpers (used for verification — no geometry engine needed)
    # ------------------------------------------------------------------

    def volume_mm3(self, shape: ShapeDescription) -> float:
        """Estimate workpiece volume (mm³) analytically from ShapeDescription."""
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
