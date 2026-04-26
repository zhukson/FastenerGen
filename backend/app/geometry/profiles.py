"""
Axisymmetric profile builders for punches and dies.

A profile is a list of (r, z) tuples in real-world mm. Both 2D drawings
(side view) and 3D meshes (revolution around Z axis) consume the same
profile, so they cannot drift.

Conventions
-----------
- Z=0 at rear (mounting end), Z=total_length at working face.
- Punch profiles are CLOSED axisymmetric contours: start at (0, z_rear) and
  return to (0, z_top), looping through the rear face → shoulder → body →
  working-face → axis.
- Die wall profiles are CLOSED polygons (full wall cross-section), not
  axis-anchored. They contain the outer cylinder edges, top/bottom faces,
  and the bore profile.

Schema field convention (matches the existing trimesh path):

  PUNCHES
    outer_diameter      = body OD (cylindrical body radius x 2)
    inner_diameter      = working tip diameter (typically < OD)
    shoulder_diameter   = retaining shoulder OD (typically > OD)
    approach_angle_deg  = full included angle of working face cone (90°=flat)
    land_length         = working tip flat length (extrusion punch)
    entry_radius        = under-shoulder fillet hint

  DIES
    outer_diameter      = die body OD
    inner_diameter      = bore ID (land diameter)
    approach_angle_deg  = entry-cone full angle from horizontal
    land_length         = straight bore length
    relief_angle_deg    = relief cone half-angle on exit side
    cavity_depth        = top forming-cavity depth (for heading dies)
    entry_radius        = top-edge break radius

The functions here are pure: no trimesh / cadquery imports.
"""

from __future__ import annotations

import math

from app.data.schemas import DieComponentParams, DieGeometryType


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _arc(
    cx: float,
    cz: float,
    radius: float,
    start_deg: float,
    end_deg: float,
    steps: int = 10,
) -> list[tuple[float, float]]:
    """Sample (r, z) points along a circular arc."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        a = math.radians(start_deg + (end_deg - start_deg) * t)
        pts.append((cx + radius * math.cos(a), cz + radius * math.sin(a)))
    return pts


def _dedupe(profile: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop consecutive duplicates (avoids zero-length segments)."""
    out: list[tuple[float, float]] = []
    for p in profile:
        if not out or (abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6):
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Punch dimensions resolution
# ---------------------------------------------------------------------------


def punch_dimensions(params: DieComponentParams) -> dict[str, float]:
    """Resolve common punch dimensions with sensible defaults."""
    od = params.outer_diameter
    wd_raw = params.inner_diameter
    if wd_raw and wd_raw < od:
        wd = wd_raw
    else:
        wd = od * 0.65

    sd = params.shoulder_diameter or od * 1.35
    if sd <= od:
        sd = od * 1.35

    total = params.working_length
    shoulder_len = min(total * 0.25, 18.0)
    body_len = max(total - shoulder_len, total * 0.5)
    shoulder_len = total - body_len

    approach = params.approach_angle_deg if params.approach_angle_deg else 90.0
    approach = min(max(approach, 10.0), 90.0)

    land = params.land_length or 0.0

    return {
        "od_r": od / 2,
        "wd_r": wd / 2,
        "sd_r": sd / 2,
        "total": total,
        "body_len": body_len,
        "shoulder_len": shoulder_len,
        "approach_deg": approach,
        "land_len": min(land, body_len * 0.6),
    }


# ---------------------------------------------------------------------------
# Punch sub-builders
# ---------------------------------------------------------------------------


def _rear_to_body_top(d: dict[str, float], face_h: float) -> list[tuple[float, float]]:
    """
    Build the rear-end + shoulder + body section of the punch up to the start
    of the working face.

    Returns a profile that:
      * starts at the axis on the rear (inside the ejector dimple)
      * exits the dimple, runs across the rear annular face,
      * goes up the shoulder, fillets onto the body OD,
      * runs along the body OD up to (od_r, total - face_h)

    The caller appends the working-face segments (must end at (0, total)).
    """
    od_r = d["od_r"]
    sd_r = d["sd_r"]
    shoulder_len = d["shoulder_len"]
    total = d["total"]

    body_top_z = total - face_h
    if body_top_z < shoulder_len + 0.5:
        # Working face would eat into the shoulder — shrink it.
        body_top_z = shoulder_len + 0.5

    # Ejector dimple — concave hemisphere recessed into the rear face.
    # Quarter-circle arc of radius R centered at (0, 0): goes from the
    # bowl apex (0, R) down to the rim (R, 0). The bowl apex is the
    # deepest point inside the punch (at z = R), and the rim sits flush
    # with the rear face (z = 0).
    dimple_r = max(0.5, min(od_r * 0.30, 4.0))

    profile: list[tuple[float, float]] = [(0.0, dimple_r)]
    profile += _arc(
        cx=0.0, cz=0.0,
        radius=dimple_r,
        start_deg=90, end_deg=0,
        steps=8,
    )
    # Now at (dimple_r, 0) — rim of the dimple, on the rear face.
    # Rear annular face out to the shoulder rim.
    profile.append((sd_r, 0.0))
    # Up the shoulder OD to the under-shoulder face.
    profile.append((sd_r, shoulder_len))

    # Concave under-shoulder fillet from the shoulder top face onto the body
    # OD. Arc center sits in the air, R radial-out from the body wall and
    # R axial-up from the shoulder top face.
    fillet_r = max(0.3, min((sd_r - od_r) * 0.5, shoulder_len * 0.3, 1.5))
    if od_r + fillet_r < sd_r:
        profile.append((od_r + fillet_r, shoulder_len))   # start of fillet
        profile += _arc(
            cx=od_r + fillet_r, cz=shoulder_len + fillet_r,
            radius=fillet_r,
            start_deg=270, end_deg=180,
            steps=6,
        )
    # Up the body OD.
    profile.append((od_r, body_top_z))

    return profile


def _flat_face_punch(d: dict[str, float]) -> list[tuple[float, float]]:
    """Plain flat-bottomed punch (geometry_type=flat_face / open_heading / default)."""
    profile = _rear_to_body_top(d, face_h=0.5)
    od_r = d["od_r"]
    total = d["total"]
    profile.append((od_r, total))
    profile.append((0.0, total))
    return _dedupe(profile)


def _countersink_punch(d: dict[str, float]) -> list[tuple[float, float]]:
    """
    Conical countersink face, e.g. for forming a flat (countersunk) head.

    Approach angle is the full included angle of the cone (e.g., 90° flat,
    100° common flat-head, 60° deep csk). With approach=90 the face is a
    pure flat — handled by _flat_face_punch instead.
    """
    od_r = d["od_r"]
    wd_r = d["wd_r"]
    total = d["total"]
    approach = d["approach_deg"]

    half = math.radians((180 - approach) / 2)
    if half <= 1e-3:
        return _flat_face_punch(d)
    cone_h = (od_r - wd_r) / math.tan(half) if math.tan(half) > 0 else 0.0
    cone_h = max(0.0, min(cone_h, d["body_len"] * 0.45))

    # Tip flat keeps small to avoid singular apex.
    tip_flat_h = max(0.3, wd_r * 0.20)
    face_h = cone_h + tip_flat_h

    profile = _rear_to_body_top(d, face_h=face_h)
    body_top = total - face_h
    profile.append((od_r, body_top))
    profile.append((wd_r, body_top + cone_h))
    profile.append((wd_r, body_top + cone_h + tip_flat_h))
    profile.append((0.0, body_top + cone_h + tip_flat_h))
    return _dedupe(profile)


def _spherical_face_punch(d: dict[str, float]) -> list[tuple[float, float]]:
    """
    Spherical dome face — for button / pan / round-head closed-heading punches.
    Sphere radius = od_r so the dome rises by od_r above the body top.
    """
    od_r = d["od_r"]
    total = d["total"]

    # Cap radius can be slightly larger than od_r for a flatter dome; clamp.
    cap_r = od_r
    cap_h = cap_r  # full hemisphere
    cap_h = min(cap_h, d["body_len"] * 0.7)
    # Recompute cap_r from cap_h if the height was clamped.
    # Sphere of true radius R, capped at h gives chord-radius od_r where
    # od_r^2 + (R - h)^2 = R^2  →  R = (od_r^2 + h^2) / (2h)
    if cap_h > 0:
        sphere_R = (od_r * od_r + cap_h * cap_h) / (2 * cap_h)
    else:
        sphere_R = od_r
    center_z = total - cap_h - (sphere_R - cap_h)  # = total - sphere_R
    # Arc from (od_r, total - cap_h) up to (0, total).
    start_angle = math.degrees(math.acos(min(max((total - cap_h - center_z) / sphere_R, -1), 1)))
    # angle measured from +z axis: start at acos(... = (R-cap_h)/R) which is the rim, end at 0 (apex)

    profile = _rear_to_body_top(d, face_h=cap_h)
    body_top = total - cap_h
    profile.append((od_r, body_top))
    # Sample arc from rim → apex.
    rim_angle = math.atan2(od_r, total - cap_h - center_z)  # angle from +z axis
    apex_angle = 0.0
    steps = 10
    for i in range(1, steps + 1):
        t = i / steps
        a = rim_angle + (apex_angle - rim_angle) * t
        r = sphere_R * math.sin(a)
        z = center_z + sphere_R * math.cos(a)
        profile.append((r, z))
    return _dedupe(profile)


def _extrusion_punch(d: dict[str, float]) -> list[tuple[float, float]]:
    """
    Long body + tapered nose to a working tip flat. Used for forward-extrusion
    punches where the nose presses material through a die.
    """
    od_r = d["od_r"]
    wd_r = d["wd_r"]
    total = d["total"]
    approach = d["approach_deg"]
    land = d["land_len"]
    if land <= 0:
        land = max(0.5, wd_r * 1.5)

    half = math.radians((180 - approach) / 2)
    if math.tan(half) > 1e-3:
        cone_h = (od_r - wd_r) / math.tan(half)
    else:
        cone_h = (od_r - wd_r) * 1.5
    cone_h = max(0.5, min(cone_h, d["body_len"] * 0.5))
    face_h = cone_h + land

    profile = _rear_to_body_top(d, face_h=face_h)
    body_top = total - face_h
    profile.append((od_r, body_top))
    profile.append((wd_r, body_top + cone_h))
    profile.append((wd_r, body_top + cone_h + land))
    profile.append((0.0, body_top + cone_h + land))
    return _dedupe(profile)


# ---------------------------------------------------------------------------
# Punch dispatcher
# ---------------------------------------------------------------------------


def build_punch_profile(params: DieComponentParams) -> list[tuple[float, float]]:
    """
    Build the axisymmetric profile of a punch as a closed contour.

    Selects archetype based on geometry_type and angles:
      flat_face / open_heading / default → flat face
      conical with approach<85 + land_length>0 → extrusion punch
      conical with approach<85           → countersink (e.g. flat-head)
      closed_heading                     → spherical dome
    """
    d = punch_dimensions(params)
    geom = params.geometry_type
    has_land = (params.land_length or 0) > 0

    if geom == DieGeometryType.closed_heading:
        return _spherical_face_punch(d)
    if geom == DieGeometryType.conical:
        if has_land:
            return _extrusion_punch(d)
        return _countersink_punch(d)
    return _flat_face_punch(d)


# ---------------------------------------------------------------------------
# Die dimensions resolution
# ---------------------------------------------------------------------------


def die_dimensions(params: DieComponentParams) -> dict[str, float]:
    """Resolve common die dimensions with sensible defaults."""
    od = params.outer_diameter
    id_ = params.inner_diameter or od * 0.30
    if id_ >= od * 0.95:
        id_ = od * 0.30

    total = params.working_length
    approach = params.approach_angle_deg if params.approach_angle_deg else 30.0
    relief = params.relief_angle_deg or 0.0
    land = params.land_length or total * 0.4
    cavity_d = params.cavity_depth or 0.0

    geom = params.geometry_type
    if geom == DieGeometryType.closed_heading:
        cavity_r = max(id_ / 2 * 1.6, od / 2 * 0.45)
        cavity_r = min(cavity_r, od / 2 * 0.75)
    elif geom == DieGeometryType.flat_face:
        cavity_r = max(id_ / 2 * 1.3, od / 2 * 0.40)
        cavity_r = min(cavity_r, od / 2 * 0.70)
    else:
        cavity_r = id_ / 2

    return {
        "od_r": od / 2,
        "id_r": id_ / 2,
        "total": total,
        "approach_deg": min(max(approach, 5.0), 89.0),
        "relief_deg": min(max(relief, 0.0), 25.0),
        "land": min(land, total * 0.85),
        "cavity_depth": min(cavity_d, total * 0.6),
        "cavity_radius": cavity_r,
        "entry_chamfer": min(
            params.entry_radius or (id_ * 0.10),
            (od - id_) * 0.20,
            total * 0.08,
            2.0,
        ),
    }


# ---------------------------------------------------------------------------
# Die sub-builders — each returns a CLOSED wall polygon (right side cross-
# section with the bore on the inside). Revolved around Z it gives the die
# body with internal cavity.
# ---------------------------------------------------------------------------


def _cylindrical_die(d: dict[str, float]) -> list[tuple[float, float]]:
    """Default: cylindrical OD + straight bore + 45° entry chamfer at top."""
    od_r = d["od_r"]
    id_r = d["id_r"]
    total = d["total"]
    ch = d["entry_chamfer"]

    # Closed polygon, walking ccw (right wall): start at outer-bottom corner.
    profile = [
        (od_r, 0.0),                 # outer-bottom
        (od_r, total),               # outer-top
        (id_r + ch, total),          # top edge after chamfer
        (id_r, total - ch),          # chamfer end at bore wall
        (id_r, 0.0),                 # bottom of bore
    ]
    return _dedupe(profile)


def _extrusion_die_3zone(d: dict[str, float]) -> list[tuple[float, float]]:
    """
    Three-zone forward extrusion die:
      Top  : entry chamfer (45°) → entry cone (approach°) → land
      Mid  : straight land (id_r, land length)
      Bot  : relief cone widening back out to a slightly larger ID

    Material enters the top, is squeezed through the cone+land, and exits
    out the bottom past the relief.
    """
    od_r = d["od_r"]
    id_r = d["id_r"]
    total = d["total"]
    ch = d["entry_chamfer"]
    land = d["land"]
    approach = d["approach_deg"]
    relief = d["relief_deg"] or 1.0

    # Z layout (top→bottom):
    #   total          → top face (entry edge)
    #   total - ch     → end of chamfer
    #   z_app_top      → top of approach cone (= total - ch)
    #   z_app_bot      → bottom of approach cone = top of land
    #   z_land_bot     → bottom of land
    #   0              → bottom face
    #
    # Approach cone widens from id_r at top of land, up to id_r_top at top.
    # We want the cone height to fill (total - ch - land - relief_h).
    # Relief cone height = up to bottom face minus land bottom.
    relief_h = max(0.5, min(total * 0.20, 6.0))
    z_land_bot = relief_h
    z_land_top = relief_h + land
    if z_land_top > total - ch - 0.5:
        # Squeeze land if needed.
        z_land_top = total - ch - 0.5
        if z_land_top <= z_land_bot:
            z_land_top = z_land_bot + 0.2

    cone_h = total - ch - z_land_top
    half_app = math.radians(approach / 2)
    if math.tan(half_app) > 0 and cone_h > 0:
        id_r_top = id_r + cone_h * math.tan(half_app)
    else:
        id_r_top = id_r + (od_r - id_r) * 0.4
    id_r_top = min(id_r_top, od_r * 0.85)

    half_rel = math.radians(relief / 2)
    if math.tan(half_rel) > 0:
        id_r_bot = id_r + relief_h * math.tan(half_rel)
    else:
        id_r_bot = id_r * 1.05
    id_r_bot = min(id_r_bot, od_r * 0.85)

    profile = [
        (od_r, 0.0),
        (od_r, total),
        (id_r_top + ch, total),                 # top edge after chamfer
        (id_r_top, total - ch),                 # end of chamfer / start of approach cone
        (id_r,    z_land_top),                  # bottom of approach cone / top of land
        (id_r,    z_land_bot),                  # bottom of land / top of relief cone
        (id_r_bot, 0.0),                        # bottom of relief cone / bottom face
    ]
    return _dedupe(profile)


def _closed_heading_die(d: dict[str, float]) -> list[tuple[float, float]]:
    """
    Heading die with closed forming cavity at the top.
    Lower 60% : straight bore (the shank passes through, ID = id_r)
    Upper 40% : forming cavity at larger radius — the head is shaped here.
    """
    od_r = d["od_r"]
    id_r = d["id_r"]
    total = d["total"]
    ch = d["entry_chamfer"]
    cavity_d = d["cavity_depth"] or total * 0.40
    cavity_d = min(cavity_d, total * 0.6)
    cavity_r = max(id_r * 1.6, od_r * 0.45)
    cavity_r = min(cavity_r, od_r * 0.75)

    z_cavity_bot = total - cavity_d

    profile = [
        (od_r, 0.0),
        (od_r, total),
        (cavity_r + ch, total),                 # top edge of cavity after chamfer
        (cavity_r, total - ch),                 # cavity wall after chamfer
        (cavity_r, z_cavity_bot),               # bottom of cavity wall
        (id_r,    z_cavity_bot),                # cavity floor (shoulder onto bore)
        (id_r,    0.0),                         # bottom of bore
    ]
    return _dedupe(profile)


def _flat_face_die(d: dict[str, float]) -> list[tuple[float, float]]:
    """
    Heading die for forming a flat / countersunk head: through bore plus a
    short flat-bottom forming pocket at the top.
    """
    od_r = d["od_r"]
    id_r = d["id_r"]
    total = d["total"]
    ch = d["entry_chamfer"]
    pocket_d = d["cavity_depth"] or total * 0.20
    pocket_d = min(pocket_d, total * 0.4)
    pocket_r = max(id_r * 1.3, od_r * 0.40)
    pocket_r = min(pocket_r, od_r * 0.70)

    z_pocket_bot = total - pocket_d

    profile = [
        (od_r, 0.0),
        (od_r, total),
        (pocket_r + ch, total),
        (pocket_r, total - ch),
        (pocket_r, z_pocket_bot),
        (id_r,    z_pocket_bot),
        (id_r,    0.0),
    ]
    return _dedupe(profile)


# ---------------------------------------------------------------------------
# Die dispatcher
# ---------------------------------------------------------------------------


def build_die_wall(params: DieComponentParams) -> list[tuple[float, float]]:
    """
    Build the die wall as a closed polygon (cross-section in the r-z plane).

    Selects archetype based on geometry_type:
      conical                    → 3-zone extrusion (entry cone + land + relief)
      closed_heading             → through bore + closed forming cavity
      flat_face                  → through bore + flat-bottom pocket
      cylindrical / stepped /
      open_heading / trimming /
      default                    → simple straight bore + chamfer
    """
    d = die_dimensions(params)
    geom = params.geometry_type

    if geom == DieGeometryType.conical:
        return _extrusion_die_3zone(d)
    if geom == DieGeometryType.closed_heading:
        return _closed_heading_die(d)
    if geom == DieGeometryType.flat_face:
        return _flat_face_die(d)
    return _cylindrical_die(d)


# ---------------------------------------------------------------------------
# Profile feature inspection (used by 2D drawing for feature dimensioning)
# ---------------------------------------------------------------------------


def punch_face_kind(params: DieComponentParams) -> str:
    """Return one of: 'flat', 'countersink', 'sphere', 'extrusion'."""
    geom = params.geometry_type
    has_land = (params.land_length or 0) > 0
    if geom == DieGeometryType.closed_heading:
        return "sphere"
    if geom == DieGeometryType.conical:
        return "extrusion" if has_land else "countersink"
    return "flat"


def die_kind(params: DieComponentParams) -> str:
    """Return one of: 'cylindrical', 'extrusion_3zone', 'closed_heading', 'flat_face'."""
    geom = params.geometry_type
    if geom == DieGeometryType.conical:
        return "extrusion_3zone"
    if geom == DieGeometryType.closed_heading:
        return "closed_heading"
    if geom == DieGeometryType.flat_face:
        return "flat_face"
    return "cylindrical"
