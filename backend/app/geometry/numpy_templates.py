"""
Parametric 3D die geometry using numpy + trimesh.

Punches and dies are axially symmetric — we define a 2D cross-section profile
and revolve it around the Z axis to get a proper closed solid mesh.

No CADQuery or OCCT required: just numpy + trimesh (both always installed).

Geometry conventions:
  - Z axis = axial direction, Z=0 at base, Z=length at working face
  - All dimensions in mm
  - Punch: solid cylinder body → approach taper → working face
  - Die:   hollow cylinder (outer wall + inner bore + entry chamfer)
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


# ---------------------------------------------------------------------------
# Core mesh primitives
# ---------------------------------------------------------------------------

def _revolve_profile(
    profile: list[tuple[float, float]],
    sections: int = 64,
    closed_bottom: bool = True,
    closed_top: bool = True,
) -> "trimesh.Trimesh":
    """
    Revolve a 2D radial profile [(r, z), ...] around the Z axis.

    The profile is the right-hand cross-section. The first point should be
    on r=0 (axis) or will be closed automatically. Returns a watertight mesh.
    """
    pts = np.array(profile, dtype=float)  # (N, 2)
    n = len(pts)

    angles = np.linspace(0, 2 * np.pi, sections, endpoint=False)

    # Build vertex grid: shape (sections, n)
    # vertex index = i*n + j
    verts = []
    for a in angles:
        ca, sa = math.cos(a), math.sin(a)
        for r, z in pts:
            verts.append([r * ca, r * sa, z])
    vertices = np.array(verts, dtype=float)

    faces = []

    # Side quads → triangles
    for i in range(sections):
        ni = (i + 1) % sections
        for j in range(n - 1):
            v0 = i * n + j
            v1 = i * n + j + 1
            v2 = ni * n + j + 1
            v3 = ni * n + j
            faces.append([v0, v2, v1])
            faces.append([v0, v3, v2])

    # Bottom cap fan (z = pts[0][1])
    if closed_bottom and pts[0, 0] == 0.0:
        # First point is on axis — already there, use it as fan center
        center_idx = 0  # first vertex of ring 0
        for i in range(sections):
            ni = (i + 1) % sections
            a = i * n      # first point of ring i  (r=0, same z)
            b = ni * n     # first point of ring ni (r=0, same z)
            # Second point (j=1) is the actual rim
            rim_a = i * n + 1
            rim_b = ni * n + 1
            faces.append([a, rim_a, rim_b])

    # Top cap fan (z = pts[-1][1])
    if closed_top and pts[-1, 0] == 0.0:
        for i in range(sections):
            ni = (i + 1) % sections
            tip_a = i * n + (n - 1)
            tip_b = ni * n + (n - 1)
            rim_a = i * n + (n - 2)
            rim_b = ni * n + (n - 2)
            faces.append([tip_a, rim_b, rim_a])

    mesh = trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)
    return mesh


def _hollow_cylinder(
    od: float,
    id_: float,
    length: float,
    entry_chamfer: float = 0.0,
    sections: int = 64,
) -> "trimesh.Trimesh":
    """
    Create a hollow cylinder (die body): outer wall + inner bore + annular caps.
    Optional entry_chamfer at the top (Z=length) inner edge.
    """
    ro = od / 2
    ri = id_ / 2
    ch = min(entry_chamfer, (ro - ri) * 0.3, length * 0.1)  # clamp chamfer

    angles = np.linspace(0, 2 * np.pi, sections, endpoint=False)
    ca = np.cos(angles)
    sa = np.sin(angles)

    def ring(r: float, z: float) -> np.ndarray:
        return np.column_stack([r * ca, r * sa, np.full(sections, z)])

    # Rings
    ob = ring(ro, 0)           # outer bottom
    ot = ring(ro, length)      # outer top
    ib = ring(ri, 0)           # inner bottom
    if ch > 0:
        ich = ring(ri + ch, length - ch)   # chamfer start
        it = ring(ri, length - ch)         # inner top (after chamfer)
        ichT = ring(ri + ch, length)       # chamfer top edge
    else:
        it = ring(ri, length)

    if ch > 0:
        vertices = np.vstack([ob, ot, ib, it, ich, ichT])
        ob_i, ot_i, ib_i, it_i, ich_i, ichT_i = (
            np.arange(sections) + k * sections
            for k in range(6)
        )
    else:
        vertices = np.vstack([ob, ot, ib, it])
        ob_i, ot_i, ib_i, it_i = (
            np.arange(sections) + k * sections
            for k in range(4)
        )

    faces = []

    def quad_strip(ring_a: np.ndarray, ring_b: np.ndarray, flip: bool = False) -> None:
        s = sections
        for i in range(s):
            j = (i + 1) % s
            a0, a1 = int(ring_a[i]), int(ring_a[j])
            b0, b1 = int(ring_b[i]), int(ring_b[j])
            if flip:
                faces.append([a0, b0, a1])
                faces.append([b0, b1, a1])
            else:
                faces.append([a0, a1, b0])
                faces.append([a1, b1, b0])

    # Outer wall
    quad_strip(ob_i, ot_i, flip=False)
    # Inner wall (normals point inward)
    quad_strip(ib_i, it_i, flip=True)
    # Bottom annular cap
    quad_strip(ob_i, ib_i, flip=True)
    # Top annular cap
    if ch > 0:
        # Annular face at top: ob_top → inner chamfer edge
        quad_strip(ot_i, ichT_i, flip=False)
        # Chamfer cone
        quad_strip(ichT_i, it_i, flip=True)
    else:
        quad_strip(ot_i, it_i, flip=False)

    mesh = trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=False)
    return mesh


# ---------------------------------------------------------------------------
# Punch geometry
# ---------------------------------------------------------------------------

def build_punch_mesh(params: "DieComponentParams") -> "trimesh.Trimesh":
    """
    Build a punch solid mesh from DieComponentParams.

    Profile (bottom → top):
      - Cylindrical body (OD, 70% of total length)
      - Approach taper (OD → working_diameter over approach zone)
      - Working face (flat or with nose radius stub)
    """
    od = params.outer_diameter
    total = params.working_length
    approach_deg = params.approach_angle_deg or 15.0
    face_r = params.entry_radius or 0.0
    # Working diameter: use inner_diameter if set, else 60-70% of OD
    wd = params.inner_diameter if (params.inner_diameter and params.inner_diameter < od) else od * 0.65

    approach_rad = math.radians(approach_deg)
    # Length of approach cone from geometry
    approach_len = (od / 2 - wd / 2) / math.tan(approach_rad) if approach_rad > 0 else od * 0.1
    approach_len = min(approach_len, total * 0.4)

    body_len = total - approach_len
    if body_len < total * 0.3:
        body_len = total * 0.3
        approach_len = total - body_len

    work_len = approach_len

    # Profile: (r, z) starting at axis bottom, going up
    profile: list[tuple[float, float]] = [
        (0.0, 0.0),                      # bottom center (axis)
        (od / 2, 0.0),                   # bottom outer edge
        (od / 2, body_len),              # shoulder
        (wd / 2, body_len + work_len),   # end of approach taper
        (0.0, total),                    # tip center
    ]

    return _revolve_profile(profile, sections=64, closed_bottom=True, closed_top=True)


# ---------------------------------------------------------------------------
# Die geometry
# ---------------------------------------------------------------------------

def build_die_mesh(params: "DieComponentParams") -> "trimesh.Trimesh":
    """
    Build a die cavity solid mesh from DieComponentParams.

    The die is a hollow cylinder:
      - Outer diameter = params.outer_diameter
      - Bore = params.inner_diameter (cavity)
      - Entry chamfer at working face
    """
    od = params.outer_diameter
    total = params.working_length
    approach_deg = params.approach_angle_deg or 30.0
    # Cavity ID: if inner_diameter not set, approximate from approach geometry
    id_ = params.inner_diameter if params.inner_diameter else od * 0.35

    # Entry chamfer depth derived from approach angle
    chamfer = min((od - id_) * 0.15, total * 0.08, 2.0)

    return _hollow_cylinder(
        od=od,
        id_=id_,
        length=total,
        entry_chamfer=chamfer,
        sections=64,
    )


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def export_stl(mesh: "trimesh.Trimesh", path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(path))
    return path
