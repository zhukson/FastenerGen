"""
Parametric 3D die geometry using numpy + trimesh.

Punches and dies are axially symmetric — we define a 2D cross-section profile
(in geometry/profiles.py) and revolve it around the Z axis to get a closed
solid mesh. Both 2D drawings and 3D meshes consume the same profile so they
cannot drift.

No CADQuery or OCCT required: just numpy + trimesh (both always installed).

Geometry conventions:
  - Z axis = axial direction, Z=0 at rear, Z=working_length at working face
  - All dimensions in mm
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False

from app.geometry.profiles import build_die_wall, build_punch_profile


# ---------------------------------------------------------------------------
# Core mesh primitives
# ---------------------------------------------------------------------------


def _revolve_closed_polygon(
    polygon: list[tuple[float, float]],
    sections: int = 64,
) -> "trimesh.Trimesh":
    """
    Revolve a CLOSED polygon (in the r-z plane) around the Z axis.

    The polygon must be a self-closing contour. The first and last points are
    treated as connected. Points exactly on the axis (r=0) collapse to a single
    3D point — the corresponding triangle pair becomes a single (non-degenerate)
    triangle. Side quads alone produce a watertight mesh; no separate cap fans
    are needed.
    """
    pts = list(polygon)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    n = len(pts) - 1  # unique points; the last duplicate is implicit via wrap

    angles = np.linspace(0, 2 * np.pi, sections, endpoint=False)
    verts = []
    for a in angles:
        ca, sa = math.cos(a), math.sin(a)
        for r, z in pts[:n]:
            verts.append([r * ca, r * sa, z])
    vertices = np.array(verts, dtype=float)

    faces: list[list[int]] = []
    for i in range(sections):
        ni = (i + 1) % sections
        for j in range(n):
            j_next = (j + 1) % n
            v0 = i * n + j
            v1 = i * n + j_next
            v2 = ni * n + j_next
            v3 = ni * n + j
            r0 = pts[j][0]
            r1 = pts[j_next][0]
            on_axis_0 = r0 < 1e-6
            on_axis_1 = r1 < 1e-6
            if on_axis_0 and on_axis_1:
                continue                      # both edges collapse to a point
            if on_axis_0:
                faces.append([v0, v2, v1])    # only one valid triangle
            elif on_axis_1:
                faces.append([v0, v3, v2])
            else:
                faces.append([v0, v2, v1])
                faces.append([v0, v3, v2])

    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=np.array(faces, dtype=np.int64),
        process=False,
    )
    # Coincident vertices on the axis (r=0) get duplicated once per section.
    # Merge them so the mesh is genuinely watertight.
    mesh.merge_vertices()
    return mesh


def _revolve_profile(
    profile: list[tuple[float, float]],
    sections: int = 64,
    closed_bottom: bool = True,
    closed_top: bool = True,
) -> "trimesh.Trimesh":
    """
    Legacy axis-anchored revolve. Kept for backward compatibility with
    callers that still use simple (axis, rim, ..., rim, axis) profiles —
    in particular workpiece.py.

    For new code (punches and dies), prefer _revolve_closed_polygon with a
    fully closed contour.
    """
    pts = np.array(profile, dtype=float)
    n = len(pts)

    angles = np.linspace(0, 2 * np.pi, sections, endpoint=False)
    verts = []
    for a in angles:
        ca, sa = math.cos(a), math.sin(a)
        for r, z in pts:
            verts.append([r * ca, r * sa, z])
    vertices = np.array(verts, dtype=float)

    faces: list[list[int]] = []
    for i in range(sections):
        ni = (i + 1) % sections
        for j in range(n - 1):
            v0 = i * n + j
            v1 = i * n + j + 1
            v2 = ni * n + j + 1
            v3 = ni * n + j
            faces.append([v0, v2, v1])
            faces.append([v0, v3, v2])

    if closed_bottom and pts[0, 0] == 0.0:
        for i in range(sections):
            ni = (i + 1) % sections
            a = i * n
            rim_a = i * n + 1
            rim_b = ni * n + 1
            faces.append([a, rim_a, rim_b])

    if closed_top and pts[-1, 0] == 0.0:
        for i in range(sections):
            ni = (i + 1) % sections
            tip_a = i * n + (n - 1)
            rim_a = i * n + (n - 2)
            rim_b = ni * n + (n - 2)
            faces.append([tip_a, rim_b, rim_a])

    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)


# ---------------------------------------------------------------------------
# Punch geometry
# ---------------------------------------------------------------------------


def build_punch_mesh(params: "DieComponentParams") -> "trimesh.Trimesh":
    """
    Build a punch solid mesh from DieComponentParams.

    Profile selection lives in profiles.py — this just revolves it.
    """
    profile = build_punch_profile(params)
    return _revolve_closed_polygon(profile, sections=72)


# ---------------------------------------------------------------------------
# Die geometry
# ---------------------------------------------------------------------------


def build_die_mesh(params: "DieComponentParams") -> "trimesh.Trimesh":
    """
    Build a die cavity solid mesh from DieComponentParams.

    The wall cross-section (closed polygon) lives in profiles.py — this just
    revolves it around the Z axis to produce the full die body.
    """
    polygon = build_die_wall(params)
    return _revolve_closed_polygon(polygon, sections=72)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def export_stl(mesh: "trimesh.Trimesh", path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(path))
    return path
