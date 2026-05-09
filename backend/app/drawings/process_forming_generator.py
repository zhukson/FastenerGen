"""Generate a 过模图 (process forming drawing) DXF from a ProcessForming JSON.

Step 4 of the v2 pipeline. Deterministic — the LLM never emits coordinates.

Visual conventions (matched to the real 过模图s in fasternerGenData/):

  - Head is drawn on the RIGHT, shank to the LEFT (cold-heading direction).
  - Each workpiece is an axisymmetric cross-section: upper-half profile +
    centerline-mirrored lower half. Fillets/chamfers are real ARCs.
  - Each workpiece has full per-feature dimensioning:
      * overall L below
      * max ⌀ on the left
      * head ⌀ + head H on the right when present
      * shank ⌀ when distinct from max
      * any extras from key_dimensions / extra_dims_mm
  - Drawing-space text is intentionally sparse. Process reasoning and cited
    cases belong in design_reasoning.md / the web UI, not in the DXF sheet.
  - No HATCH entities in the process drawing; real factory 过模图s here use
    outline/detail geometry and dimensions rather than CAD hatch fills.
  - >4 stations wrap to a second row (matches the real drawings).
  - Compact factory-style title block: 单号 / 机型 / 产品名称.
  - Dimension text uses `<>` so ezdxf auto-fills the measurement (no
    hard-coded numerics that drift from geometry).
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.document import Drawing as DXFDocument

from app.data.schemas import (
    ProcessForming,
    ProfileSegment,
    TitleBlock,
    WorkpieceGeometry,
)
from app.drawings.standards import (
    DRAWING_SIZES,
    DrawingFrame,
    setup_dimension_style,
    setup_layers,
    setup_text_styles,
)

# Layout (mm in paper space)
STATIONS_PER_ROW_LIMIT = 4
ROW_VERTICAL_GAP = 90.0
WORKPIECE_BAND_TOP_MARGIN = 70.0
INTER_STATION_PADDING = 8.0     # gap between station cells; dims live inside cells
CELL_LEFT_DIM_ALLOWANCE = 42.0
CELL_RIGHT_DIM_ALLOWANCE = 66.0
CELL_INNER_MARGIN = 5.0
DIM_OFFSET_BELOW = 12.0
DIM_OFFSET_ABOVE = 10.0
DIM_OFFSET_LEFT = 10.0
DIM_OFFSET_RIGHT = 10.0
STATION_NUMBER_RADIUS = 4.0
STATION_NUMBER_GAP = 18.0       # above the workpiece outline

# Real 过模图s exaggerate the radial axis so features are legible —
# a long bolt can be only ~15mm wide × 100mm long, which would render as a thin line.
# We scale Y (radial) more than X (axial) by this factor so the workpiece
# silhouettes are recognizable instead of looking like centerlines.
RADIAL_EXAGGERATION = 5.0


# ---------------------------------------------------------------------------
# Profile builders — return (segments, max_y) where each segment is one of:
#   ("L", (x1,y1), (x2,y2))                     -- straight line
#   ("A", (cx,cy), radius, start_deg, end_deg)  -- arc, CCW from start to end
# All in workpiece-local coordinates (x = axial, y = radial; y >= 0 = upper half).
# Head is on the RIGHT (high x); shank/blank wire stock to the LEFT (low x).
# ---------------------------------------------------------------------------


Segment = tuple


def _profile_cylinder(L: float, R: float) -> tuple[list[Segment], float]:
    return [
        ("L", (0.0, R), (L, R)),
        ("L", (0.0, 0.0), (0.0, R)),       # left end cap
        ("L", (L, 0.0), (L, R)),           # right end cap
    ], R


def _profile_headed(
    L: float, max_R: float,
    head_R: float, head_H: float,
    shank_R: float, fillet: float = 0.0,
) -> tuple[list[Segment], float]:
    """Head on the RIGHT, shank to the LEFT.

    Profile (upper half), traversed left -> right -> top -> back to left:
      shank top:   (0, shank_R) -> (L-head_H, shank_R)
      undercut:    optional fillet ARC (R) up to head bottom radius
      head body:   (L-head_H, head_R) -> (L, head_R)
      head face:   (L, head_R) -> (L, 0) (drawn separately as end cap)
    """
    head_R = head_R or max_R
    shank_R = shank_R or max(head_R * 0.55, 1.0)
    head_H = head_H or min(L * 0.3, head_R * 0.9)
    shank_L = max(L - head_H, 1.0)
    segs: list[Segment] = [
        # left end cap
        ("L", (0.0, 0.0), (0.0, shank_R)),
        # shank top
        ("L", (0.0, shank_R), (shank_L, shank_R)),
    ]
    if fillet > 0 and head_R - shank_R > fillet:
        # Concave undercut fillet from shank top up to head underside.
        cx = shank_L
        cy = shank_R + fillet
        segs.append(("A", (cx, cy), fillet, 270.0, 360.0))
        # vertical from (shank_L + fillet, shank_R + fillet) up to (shank_L + fillet, head_R)
        segs.append(("L", (shank_L + fillet, shank_R + fillet), (shank_L + fillet, head_R)))
        segs.append(("L", (shank_L + fillet, head_R), (L, head_R)))
    else:
        # square shoulder
        segs.append(("L", (shank_L, shank_R), (shank_L, head_R)))
        segs.append(("L", (shank_L, head_R), (L, head_R)))
    # right end cap
    segs.append(("L", (L, 0.0), (L, head_R)))
    return segs, head_R


def _profile_stepped(
    L: float, max_R: float, shank_R: float, shank_L: float,
) -> tuple[list[Segment], float]:
    """Two-diameter rod, larger on the LEFT, smaller (shank) on the RIGHT."""
    shank_R = shank_R or max_R * 0.6
    shank_L = shank_L or L * 0.5
    big_L = max(L - shank_L, 1.0)
    return [
        ("L", (0.0, 0.0), (0.0, max_R)),
        ("L", (0.0, max_R), (big_L, max_R)),
        ("L", (big_L, max_R), (big_L, shank_R)),
        ("L", (big_L, shank_R), (L, shank_R)),
        ("L", (L, 0.0), (L, shank_R)),
    ], max_R


def _profile_tapered(L: float, max_R: float) -> tuple[list[Segment], float]:
    """Pointed tip on the right."""
    return [
        ("L", (0.0, 0.0), (0.0, max_R)),
        ("L", (0.0, max_R), (L * 0.7, max_R)),
        ("L", (L * 0.7, max_R), (L, 0.0)),
    ], max_R


def _profile_pin(L: float, max_R: float) -> tuple[list[Segment], float]:
    """Short cylinder with chamfers on both ends."""
    c = min(L * 0.08, max_R * 0.3, 1.0)
    return [
        ("L", (0.0, 0.0), (0.0, max_R - c)),
        ("L", (0.0, max_R - c), (c, max_R)),
        ("L", (c, max_R), (L - c, max_R)),
        ("L", (L - c, max_R), (L, max_R - c)),
        ("L", (L, 0.0), (L, max_R - c)),
    ], max_R


def _profile_from_segments(profile_segments: list[ProfileSegment]) -> tuple[list[Segment], float, float]:
    """Build a side profile from explicit axial segments.

    Each segment describes its start diameter and optional end diameter. The
    renderer keeps this intentionally conservative: straight/tapered top lines
    plus vertical shoulders. Fillets/chamfers are retained as fields for future
    callouts, but not forced into geometry unless they are unambiguous.
    """
    usable = [s for s in profile_segments if s.length_mm > 0 and s.diameter_mm > 0]
    if not usable:
        return _profile_cylinder(1.0, 1.0)

    x = 0.0
    first_r = usable[0].diameter_mm / 2.0
    current_r = first_r
    ymax = first_r
    segs: list[Segment] = [("L", (0.0, 0.0), (0.0, first_r))]

    for idx, seg in enumerate(usable):
        start_r = seg.diameter_mm / 2.0
        end_r = (seg.end_diameter_mm if seg.end_diameter_mm is not None else seg.diameter_mm) / 2.0
        if abs(current_r - start_r) > 0.01:
            segs.append(("L", (x, current_r), (x, start_r)))
        x2 = x + seg.length_mm
        segs.append(("L", (x, start_r), (x2, end_r)))
        x = x2
        current_r = end_r
        ymax = max(ymax, start_r, end_r)

        if idx + 1 < len(usable):
            next_r = usable[idx + 1].diameter_mm / 2.0
            if abs(current_r - next_r) > 0.01:
                segs.append(("L", (x, current_r), (x, next_r)))
                current_r = next_r

    segs.append(("L", (x, 0.0), (x, current_r)))
    return segs, ymax, x


def _build_profile(w: WorkpieceGeometry) -> tuple[list[Segment], float, float]:
    """Dispatch to a profile builder. Returns (segments, max_y, total_x)."""
    if w.profile_segments:
        return _profile_from_segments(w.profile_segments)

    L = float(w.overall_length_mm or 1.0)
    R = float(w.max_diameter_mm or 1.0) / 2.0
    head_R = (w.head_diameter_mm or 0.0) / 2.0
    head_H = w.head_height_mm or 0.0
    shank_R = (w.shank_diameter_mm or 0.0) / 2.0
    shank_L = w.shank_length_mm or 0.0

    if L <= 0 or R <= 0:
        # Degenerate fallback so the layout still renders something.
        L, R = max(L, 6.0), max(R, 1.5)

    t = w.type
    if t in ("headed", "T_head", "square_head", "flanged"):
        # T_head: head height tends to be small relative to head_R; flanged
        # is typically a thin disc. We render all three with the same shape;
        # the visual cue is in the H/D ratio.
        fillet = _numeric_attr(w, "fillet_r_mm", "fillet_R", "R", default=0.0)
        # For flanged / pre-trim stations, max_diameter_mm often means flash
        # or flange OD. Keep that wider contour visible instead of shrinking
        # the profile to head_diameter_mm.
        profile_head_R = R if t == "flanged" else (head_R or R)
        segs, ymax = _profile_headed(L, R, profile_head_R, head_H, shank_R, fillet)
    elif t == "stepped":
        segs, ymax = _profile_stepped(L, R, shank_R, shank_L)
    elif t == "tapered":
        segs, ymax = _profile_tapered(L, R)
    elif t == "pin":
        segs, ymax = _profile_pin(L, R)
    else:  # "cylinder" or "custom"
        segs, ymax = _profile_cylinder(L, R)
    return segs, ymax, L


def _numeric_attr(w: WorkpieceGeometry, *names: str, default: float | None = None) -> float | None:
    """Find the first numeric geometry value from direct attrs or extra_dims."""
    for name in names:
        value = getattr(w, name, None)
        if isinstance(value, int | float):
            return float(value)
    extra = w.extra_dims_mm or {}
    for name in names:
        value = extra.get(name)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value)
            if match:
                return float(match.group(0))
    return default


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def _draw_segments(
    msp: Any, segs: list[Segment], *, ox: float, oy: float, mirror: bool, layer: str,
) -> None:
    sign = -1.0 if mirror else 1.0
    for seg in segs:
        if seg[0] == "L":
            (x1, y1), (x2, y2) = seg[1], seg[2]
            msp.add_line(
                (ox + x1, oy + sign * y1),
                (ox + x2, oy + sign * y2),
                dxfattribs={"layer": layer},
            )
        elif seg[0] == "A":
            (cx, cy), r, sa, ea = seg[1], seg[2], seg[3], seg[4]
            # Mirror an arc by negating the y-center and swapping start/end
            # angles around the x-axis.
            if mirror:
                msp.add_arc(
                    center=(ox + cx, oy - cy),
                    radius=r,
                    start_angle=-ea,
                    end_angle=-sa,
                    dxfattribs={"layer": layer},
                )
            else:
                msp.add_arc(
                    center=(ox + cx, oy + cy),
                    radius=r,
                    start_angle=sa,
                    end_angle=ea,
                    dxfattribs={"layer": layer},
                )


def _first_dim(
    w: WorkpieceGeometry,
    key_dimensions: dict[str, float],
    *names: str,
    default: float | None = None,
) -> float | None:
    """Read a numeric dimension from WorkpieceGeometry, key_dimensions, or extra_dims."""
    for name in names:
        value = getattr(w, name, None)
        if isinstance(value, int | float):
            return float(value)
    for name in names:
        value = key_dimensions.get(name)
        if isinstance(value, int | float):
            return float(value)
    extra = w.extra_dims_mm or {}
    for name in names:
        value = extra.get(name)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value)
            if match:
                return float(match.group(0))
    return default


def _display_scales(w: WorkpieceGeometry, *, max_y: float, length: float) -> tuple[float, float]:
    l_real = float(w.overall_length_mm or 0.0)
    d_real = float(w.max_diameter_mm or 0.0)
    x_scale = length / l_real if l_real > 0 else 1.0
    y_scale = max_y / (d_real / 2.0) if d_real > 0 else 1.0
    return x_scale, y_scale


def _draw_internal_features(
    msp: Any,
    *,
    w: WorkpieceGeometry,
    key_dimensions: dict[str, float],
    ox: float,
    oy: float,
    max_y: float,
    length: float,
) -> None:
    """Draw axial holes and blind head recesses as real geometry, not notes."""
    x_scale, y_scale = _display_scales(w, max_y=max_y, length=length)

    hole_d = _first_dim(
        w,
        key_dimensions,
        "through_hole_diameter_mm",
        "hole_D",
        "hole_diameter_mm",
        "孔径",
    )
    if hole_d and hole_d > 0:
        hole_r = min(hole_d / 2.0 * y_scale, max_y * 0.85)
        msp.add_line((ox, oy + hole_r), (ox + length, oy + hole_r), dxfattribs={"layer": "HIDDEN"})
        msp.add_line((ox, oy - hole_r), (ox + length, oy - hole_r), dxfattribs={"layer": "HIDDEN"})
        msp.add_line((ox, oy + hole_r), (ox, oy - hole_r), dxfattribs={"layer": "HIDDEN"})
        msp.add_line((ox + length, oy + hole_r), (ox + length, oy - hole_r), dxfattribs={"layer": "HIDDEN"})

    recess_d = _first_dim(
        w,
        key_dimensions,
        "head_recess_diameter_mm",
        "recess_D",
        "socket_D",
        "hex_socket_D",
        "drive_D",
    )
    recess_depth = _first_dim(
        w,
        key_dimensions,
        "head_recess_depth_mm",
        "recess_depth",
        "socket_depth",
        "drive_depth",
    )
    if recess_d and recess_depth and recess_d > 0 and recess_depth > 0:
        recess_r = min(recess_d / 2.0 * y_scale, max_y * 0.82)
        x0 = ox + max(length - recess_depth * x_scale, 0.0)
        x1 = ox + length
        msp.add_line((x0, oy + recess_r), (x1, oy + recess_r), dxfattribs={"layer": "OUTLINE"})
        msp.add_line((x0, oy - recess_r), (x1, oy - recess_r), dxfattribs={"layer": "OUTLINE"})
        msp.add_line((x0, oy - recess_r), (x0, oy + recess_r), dxfattribs={"layer": "OUTLINE"})


def _draw_plan_view(
    msp: Any,
    *,
    w: WorkpieceGeometry,
    key_dimensions: dict[str, float],
    notes: str | None,
    ox: float,
    oy: float,
    max_y: float,
    length: float,
) -> None:
    """Add compact top views for square/flanged/recessed heads when known."""
    _, y_scale = _display_scales(w, max_y=max_y, length=length)
    text_blob = f"{w.type} {notes or ''} {' '.join(key_dimensions)}"
    has_square_plan = bool(re.search(r"四方|square|head_W|flat_W", text_blob, flags=re.IGNORECASE))
    has_recess_or_hole = bool(
        _first_dim(w, key_dimensions, "head_recess_diameter_mm", "recess_D")
        or _first_dim(w, key_dimensions, "through_hole_diameter_mm", "hole_D")
    )
    if not has_square_plan and not has_recess_or_hole:
        return

    cx = ox + length / 2.0
    cy = oy + max_y + 22.0
    outer_d = _first_dim(w, key_dimensions, "head_W", "flat_W", "head_diameter_mm", default=w.max_diameter_mm)
    if not outer_d or outer_d <= 0:
        return
    half = max(outer_d / 2.0 * y_scale, 2.5)

    if has_square_plan:
        corner_r = _first_dim(w, key_dimensions, "corner_radius_mm", "corner_R", "R", default=None)
        if not corner_r and notes:
            match = re.search(r"R\s*(\d+(?:\.\d+)?)", notes)
            corner_r = float(match.group(1)) if match else None
        r = min((corner_r or outer_d * 0.08) * y_scale, half * 0.35)
        x0, x1 = cx - half, cx + half
        y0, y1 = cy - half, cy + half
        msp.add_line((x0 + r, y1), (x1 - r, y1), dxfattribs={"layer": "OUTLINE"})
        msp.add_line((x1, y1 - r), (x1, y0 + r), dxfattribs={"layer": "OUTLINE"})
        msp.add_line((x1 - r, y0), (x0 + r, y0), dxfattribs={"layer": "OUTLINE"})
        msp.add_line((x0, y0 + r), (x0, y1 - r), dxfattribs={"layer": "OUTLINE"})
        msp.add_arc((x1 - r, y1 - r), r, 0, 90, dxfattribs={"layer": "OUTLINE"})
        msp.add_arc((x0 + r, y1 - r), r, 90, 180, dxfattribs={"layer": "OUTLINE"})
        msp.add_arc((x0 + r, y0 + r), r, 180, 270, dxfattribs={"layer": "OUTLINE"})
        msp.add_arc((x1 - r, y0 + r), r, 270, 360, dxfattribs={"layer": "OUTLINE"})
        if corner_r:
            dim = msp.add_radius_dim(
                center=(x1 - r, y1 - r),
                radius=r,
                angle=45,
                location=(x1 + r * 1.8, y1 + r * 1.2),
                text=f"R{corner_r:g}",
                dimstyle="GB",
                dxfattribs={"layer": "DIMENSION"},
            )
            dim.render()
    else:
        msp.add_circle((cx, cy), half, dxfattribs={"layer": "OUTLINE"})

    inner_d = _first_dim(
        w,
        key_dimensions,
        "through_hole_diameter_mm",
        "head_recess_diameter_mm",
        "hole_D",
        "recess_D",
    )
    if inner_d and inner_d > 0:
        msp.add_circle((cx, cy), min(inner_d / 2.0 * y_scale, half * 0.82), dxfattribs={"layer": "HIDDEN"})


def _add_centerline(msp: Any, *, ox: float, oy: float, length: float) -> None:
    margin = max(length * 0.08, 4.0)
    msp.add_line(
        (ox - margin, oy), (ox + length + margin, oy),
        dxfattribs={"layer": "CENTER"},
    )


def _add_station_number(
    msp: Any, *, n: int, ox: float, oy_top: float, length: float,
) -> None:
    cx = ox + length / 2.0
    cy = oy_top + STATION_NUMBER_GAP
    msp.add_circle(
        (cx, cy), STATION_NUMBER_RADIUS,
        dxfattribs={"layer": "TEXT"},
    )
    msp.add_text(
        str(n),
        dxfattribs={
            "layer": "TEXT", "style": "GB_NOTE", "height": 3.0,
            "insert": (cx - 1.0, cy - 1.5),
        },
    )


def _add_dim(
    msp: Any, *, p1: tuple[float, float], p2: tuple[float, float],
    distance: float = 0.0, prefix: str = "", style: str = "GB",
) -> None:
    """Add a linear dimension with text='<>' so ezdxf auto-fills measurement.

    `prefix` lets us put the ⌀ symbol on diameter dims.
    """
    text = f"{prefix}<>" if prefix else "<>"
    dim = msp.add_aligned_dim(
        p1=p1, p2=p2, distance=distance,
        dimstyle=style, text=text,
        dxfattribs={"layer": "DIMENSION"},
    )
    dim.render()


def _draw_workpiece_dims(
    msp: Any, w: WorkpieceGeometry, *, ox: float, oy: float, max_y: float,
) -> None:
    L = float(w.overall_length_mm or 0.0)
    R = float(w.max_diameter_mm or 0.0) / 2.0
    if L <= 0 or R <= 0:
        return

    # Length below
    _add_dim(
        msp,
        p1=(ox, oy - max_y - DIM_OFFSET_BELOW),
        p2=(ox + L, oy - max_y - DIM_OFFSET_BELOW),
    )

    # Max diameter on left
    _add_dim(
        msp,
        p1=(ox - DIM_OFFSET_LEFT, oy - R),
        p2=(ox - DIM_OFFSET_LEFT, oy + R),
        prefix="%%C",
    )

    # Head ⌀ + head H on the right (only if distinct from max)
    head_R = (w.head_diameter_mm or 0.0) / 2.0
    head_H = w.head_height_mm or 0.0
    if head_R > 0 and head_H > 0 and head_R != R:
        _add_dim(
            msp,
            p1=(ox + L + DIM_OFFSET_RIGHT, oy - head_R),
            p2=(ox + L + DIM_OFFSET_RIGHT, oy + head_R),
            prefix="%%C",
        )
        # head height as a small length dim above the workpiece
        head_x_start = ox + max(L - head_H, 0.0)
        _add_dim(
            msp,
            p1=(head_x_start, oy + head_R + DIM_OFFSET_ABOVE),
            p2=(ox + L, oy + head_R + DIM_OFFSET_ABOVE),
        )

    # Shank ⌀ when smaller than max (stepped / headed)
    shank_R = (w.shank_diameter_mm or 0.0) / 2.0
    if shank_R > 0 and shank_R < R - 0.05:
        # On the right side but BELOW the head-⌀ dim, indicating shank section
        shank_dim_y_offset = DIM_OFFSET_RIGHT + 12.0
        _add_dim(
            msp,
            p1=(ox + L + shank_dim_y_offset, oy - shank_R),
            p2=(ox + L + shank_dim_y_offset, oy + shank_R),
            prefix="%%C",
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _operation_label_zh(op: str) -> str:
    return {
        "forward_extrusion": "正挤压",
        "backward_extrusion": "反挤压",
        "upsetting": "镦粗",
        "heading": "成形头部",
        "trimming": "切边",
        "piercing": "冲孔",
        "combined": "复合工序",
    }.get(op, op)


def _choose_paper_size(n_workpieces: int, max_workpiece_w: float) -> str:
    """Pick paper based on layout footprint."""
    rows = math.ceil(n_workpieces / STATIONS_PER_ROW_LIMIT)
    if rows == 1 and n_workpieces <= 3 and max_workpiece_w < 60:
        return "A3"
    if rows <= 2 and max_workpiece_w < 80:
        return "A2"
    return "A1"


def render_process_forming_dxf(
    forming: ProcessForming,
    *,
    output_path: Path,
    case_id: str | None = None,
    paper_size: str | None = None,
) -> Path:
    # All workpieces in display order: blank, then each station's output
    workpieces: list[tuple[int, WorkpieceGeometry, dict[str, float], str | None]] = [
        (0, forming.blank, {}, None),
    ]
    for st in forming.stations:
        workpieces.append((st.n, st.workpiece, st.key_dimensions, st.notes_zh))

    n = len(workpieces)
    max_wp_w = max((w.overall_length_mm or 0.0) for _, w, _, _ in workpieces) or 1.0
    max_wp_h = max((w.max_diameter_mm or 0.0) for _, w, _, _ in workpieces) or 1.0

    paper = paper_size or _choose_paper_size(n, max_wp_w)
    paper_w, paper_h = DRAWING_SIZES.get(paper, DRAWING_SIZES["A2"])

    # Determine layout scales — separate axial (x) and radial (y).
    # Radial is exaggerated by RADIAL_EXAGGERATION so a thin bolt's diameter
    # is visually present rather than disappearing into the centerline.
    rows = math.ceil(n / STATIONS_PER_ROW_LIMIT)
    cols = min(n, STATIONS_PER_ROW_LIMIT)
    available_w = paper_w - 60.0 - (cols - 1) * INTER_STATION_PADDING
    cell_w_for_scale = available_w / max(cols, 1)
    cell_visual_w = max(cell_w_for_scale - CELL_LEFT_DIM_ALLOWANCE - CELL_RIGHT_DIM_ALLOWANCE, 18.0)
    x_scale = min(1.0, cell_visual_w / max_wp_w)
    available_h_per_row = (paper_h - 110.0) / max(rows, 1) - ROW_VERTICAL_GAP
    needed_h_per_row = max_wp_h * RADIAL_EXAGGERATION + 30.0
    y_scale = min(x_scale * RADIAL_EXAGGERATION, available_h_per_row / needed_h_per_row * RADIAL_EXAGGERATION)
    if y_scale < x_scale:
        y_scale = x_scale  # never compress radial below axial
    doc: DXFDocument = ezdxf.new(setup="all")
    setup_layers(doc)
    setup_text_styles(doc)
    setup_dimension_style(doc, "GB")
    msp = doc.modelspace()
    frame = DrawingFrame().draw(msp, paper_size=paper)
    fx0, fy0, fx1, fy1 = frame

    # Layout: top row at fy1 - WORKPIECE_BAND_TOP_MARGIN, additional rows below.
    row_height = (max_wp_h * y_scale) + ROW_VERTICAL_GAP
    row_centers_y = [
        fy1 - WORKPIECE_BAND_TOP_MARGIN - max_wp_h * y_scale / 2 - r * row_height
        for r in range(rows)
    ]

    for i, (_station_n, w, key_dimensions, notes) in enumerate(workpieces):
        row = i // STATIONS_PER_ROW_LIMIT
        col = i % STATIONS_PER_ROW_LIMIT
        col_count = min(STATIONS_PER_ROW_LIMIT, n - row * STATIONS_PER_ROW_LIMIT)
        # Center station cells horizontally. Each cell reserves left/right
        # bands for diameter callouts, so dimensions do not invade neighbors.
        frame_w = fx1 - fx0
        base_cell_w = (
            frame_w
            - 2 * CELL_INNER_MARGIN
            - (STATIONS_PER_ROW_LIMIT - 1) * INTER_STATION_PADDING
        ) / STATIONS_PER_ROW_LIMIT
        row_total_w = col_count * base_cell_w + (col_count - 1) * INTER_STATION_PADDING
        row_x0 = fx0 + (frame_w - row_total_w) / 2.0
        cell_x0 = row_x0 + col * (base_cell_w + INTER_STATION_PADDING)
        visual_w = (w.overall_length_mm or 0.0) * x_scale
        ox = (
            cell_x0
            + CELL_LEFT_DIM_ALLOWANCE
            + max((base_cell_w - CELL_LEFT_DIM_ALLOWANCE - CELL_RIGHT_DIM_ALLOWANCE - visual_w) / 2, 0)
        )
        oy = row_centers_y[row]

        # Build SCALED workpiece for the visual: x by axial scale, y by
        # exaggerated radial scale. Real-valued dims are emitted separately.
        scaled_profile_segments = [
            seg.model_copy(update={
                "length_mm": seg.length_mm * x_scale,
                "diameter_mm": seg.diameter_mm * y_scale,
                "end_diameter_mm": (
                    seg.end_diameter_mm * y_scale if seg.end_diameter_mm is not None else None
                ),
                "fillet_r_mm": seg.fillet_r_mm * y_scale if seg.fillet_r_mm else None,
                "chamfer_c_mm": seg.chamfer_c_mm * y_scale if seg.chamfer_c_mm else None,
            })
            for seg in w.profile_segments
        ]
        scaled = w.model_copy(update={
            "overall_length_mm": (w.overall_length_mm or 0.0) * x_scale,
            "max_diameter_mm": (w.max_diameter_mm or 0.0) * y_scale,
            "head_diameter_mm": ((w.head_diameter_mm or 0.0) * y_scale) or None,
            "head_height_mm": ((w.head_height_mm or 0.0) * x_scale) or None,
            "shank_diameter_mm": ((w.shank_diameter_mm or 0.0) * y_scale) or None,
            "shank_length_mm": ((w.shank_length_mm or 0.0) * x_scale) or None,
            "fillet_r_mm": ((w.fillet_r_mm or 0.0) * y_scale) or None,
            "profile_segments": scaled_profile_segments,
        })
        segs, max_y, length = _build_profile(scaled)

        _add_centerline(msp, ox=ox, oy=oy, length=length)
        _draw_segments(msp, segs, ox=ox, oy=oy, mirror=False, layer="OUTLINE")
        _draw_segments(msp, segs, ox=ox, oy=oy, mirror=True, layer="OUTLINE")
        _draw_internal_features(
            msp, w=w, key_dimensions=key_dimensions, ox=ox, oy=oy, max_y=max_y, length=length,
        )
        _draw_plan_view(
            msp,
            w=w,
            key_dimensions=key_dimensions,
            notes=notes,
            ox=ox,
            oy=oy,
            max_y=max_y,
            length=length,
        )

        # Dimensions reflect REAL (unscaled) values via auto-measurement.
        # We pass the *scaled* geometry positions but the dim text shows
        # `<>` -> ezdxf calculates from scaled coords, so we manually pass
        # the real measurement in the override:
        _draw_real_dims(
            msp,
            w=w,
            key_dimensions=key_dimensions,
            ox=ox,
            oy=oy,
            max_y=max_y,
            length=length,
        )

    # Title block — compact process-drawing variant matching the factory cases.
    tb_data = TitleBlock(
        part_number=case_id or forming.part_name_zh,
        title=forming.part_name_zh,
    )
    _draw_compact_process_title_block(
        msp,
        frame,
        data=tb_data,
        machine_model=_infer_machine_model(case_id=case_id, forming=forming),
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))
    return output_path


def _draw_real_dims(
    msp: Any,
    *,
    w: WorkpieceGeometry,
    key_dimensions: dict[str, float],
    ox: float,
    oy: float,
    max_y: float,
    length: float,
) -> None:
    """Emit dims with override text containing the REAL (unscaled) values.

    We can't use `<>` auto-measurement because the *displayed* geometry is
    scaled to fit the page — but the engineering dims must show real mm.
    """
    L_real = float(w.overall_length_mm or 0.0)
    D_real = float(w.max_diameter_mm or 0.0)
    R_real = D_real / 2.0
    if L_real <= 0 or D_real <= 0:
        return

    # Length below
    dim = msp.add_aligned_dim(
        p1=(ox, oy - max_y - DIM_OFFSET_BELOW),
        p2=(ox + length, oy - max_y - DIM_OFFSET_BELOW),
        distance=0,
        dimstyle="GB",
        text=f"{L_real:g}",
        dxfattribs={"layer": "DIMENSION"},
    )
    dim.render()

    # Max ⌀ on left
    dim = msp.add_aligned_dim(
        p1=(ox - DIM_OFFSET_LEFT, oy - max_y),
        p2=(ox - DIM_OFFSET_LEFT, oy + max_y),
        distance=0,
        dimstyle="GB",
        text=f"%%C{D_real:g}",
        dxfattribs={"layer": "DIMENSION"},
    )
    dim.render()

    # Head ⌀ on the right (when distinct)
    head_d = float(w.head_diameter_mm or 0.0)
    head_h = float(w.head_height_mm or 0.0)
    if head_d > 0 and head_d != D_real:
        head_R_disp = head_d / 2.0 * (max_y / R_real)  # scale along y
        dim = msp.add_aligned_dim(
            p1=(ox + length + DIM_OFFSET_RIGHT, oy - head_R_disp),
            p2=(ox + length + DIM_OFFSET_RIGHT, oy + head_R_disp),
            distance=0,
            dimstyle="GB",
            text=f"%%C{head_d:g}",
            dxfattribs={"layer": "DIMENSION"},
        )
        dim.render()
        if head_h > 0:
            head_x_start = ox + max(length - head_h * (length / L_real), 0.0)
            dim = msp.add_aligned_dim(
                p1=(head_x_start, oy + max_y + DIM_OFFSET_ABOVE),
                p2=(ox + length, oy + max_y + DIM_OFFSET_ABOVE),
                distance=0,
                dimstyle="GB",
                text=f"{head_h:g}",
                dxfattribs={"layer": "DIMENSION"},
            )
            dim.render()

    # Shank ⌀ (when smaller than max)
    shank_d = float(w.shank_diameter_mm or 0.0)
    if shank_d > 0 and shank_d < D_real - 0.05:
        shank_R_disp = shank_d / 2.0 * (max_y / R_real)
        x_off = DIM_OFFSET_RIGHT + 14.0
        dim = msp.add_aligned_dim(
            p1=(ox + length + x_off, oy - shank_R_disp),
            p2=(ox + length + x_off, oy + shank_R_disp),
            distance=0,
            dimstyle="GB",
            text=f"%%C{shank_d:g}",
            dxfattribs={"layer": "DIMENSION"},
        )
        dim.render()

    # Shank length: important on real 过模图s and available in most plans.
    shank_l = float(w.shank_length_mm or key_dimensions.get("shank_L") or 0.0)
    if shank_l > 0 and shank_l < L_real - 0.05:
        x_scale = length / L_real
        dim = msp.add_aligned_dim(
            p1=(ox, oy - max_y - DIM_OFFSET_BELOW - 9.0),
            p2=(ox + shank_l * x_scale, oy - max_y - DIM_OFFSET_BELOW - 9.0),
            distance=0,
            dimstyle="GB",
            text=f"{shank_l:g}",
            dxfattribs={"layer": "DIMENSION"},
        )
        dim.render()

    # Through-hole/recess diameters and recess depth become actual callouts.
    hole_d = _first_dim(w, key_dimensions, "through_hole_diameter_mm", "hole_D")
    right_dim_x = ox + length + DIM_OFFSET_RIGHT + 28.0
    if hole_d and hole_d > 0:
        hole_r_disp = min(hole_d / 2.0 * (max_y / R_real), max_y * 0.85)
        dim = msp.add_aligned_dim(
            p1=(right_dim_x, oy - hole_r_disp),
            p2=(right_dim_x, oy + hole_r_disp),
            distance=0,
            dimstyle="GB",
            text=f"%%C{hole_d:g}",
            dxfattribs={"layer": "DIMENSION"},
        )
        dim.render()

    recess_d = _first_dim(w, key_dimensions, "head_recess_diameter_mm", "recess_D")
    recess_depth = _first_dim(w, key_dimensions, "head_recess_depth_mm", "recess_depth")
    if recess_d and recess_d > 0:
        recess_r_disp = min(recess_d / 2.0 * (max_y / R_real), max_y * 0.82)
        dim = msp.add_aligned_dim(
            p1=(right_dim_x + 11.0, oy - recess_r_disp),
            p2=(right_dim_x + 11.0, oy + recess_r_disp),
            distance=0,
            dimstyle="GB",
            text=f"%%C{recess_d:g}",
            dxfattribs={"layer": "DIMENSION"},
        )
        dim.render()
    if recess_depth and recess_depth > 0:
        x_scale = length / L_real
        x0 = ox + max(length - recess_depth * x_scale, 0.0)
        y = oy + max_y + DIM_OFFSET_ABOVE + 10.0
        dim = msp.add_aligned_dim(
            p1=(x0, y),
            p2=(ox + length, y),
            distance=0,
            dimstyle="GB",
            text=f"{recess_depth:g}",
            dxfattribs={"layer": "DIMENSION"},
        )
        dim.render()

    _draw_profile_segment_dims(
        msp,
        w=w,
        ox=ox,
        oy=oy,
        max_y=max_y,
        length=length,
        already_labeled_diameters=[D_real, head_d, shank_d],
    )


def _draw_profile_segment_dims(
    msp: Any,
    *,
    w: WorkpieceGeometry,
    ox: float,
    oy: float,
    max_y: float,
    length: float,
    already_labeled_diameters: list[float],
) -> None:
    """Add fine-grained segment length and diameter dimensions."""
    segments = [s for s in w.profile_segments if s.length_mm > 0 and s.diameter_mm > 0]
    if len(segments) < 2:
        return

    x_scale, y_scale = _display_scales(w, max_y=max_y, length=length)

    # Chain dimensions below the overall length. Cap at five segments to avoid
    # turning the demo drawing into a barcode.
    y_dim = oy - max_y - DIM_OFFSET_BELOW - 18.0
    x_cursor = ox
    for seg in segments[:5]:
        seg_len = seg.length_mm
        x_next = x_cursor + seg_len * x_scale
        if x_next - x_cursor >= 3.0:
            dim = msp.add_aligned_dim(
                p1=(x_cursor, y_dim),
                p2=(x_next, y_dim),
                distance=0,
                dimstyle="GB",
                text=f"{seg_len:g}",
                dxfattribs={"layer": "DIMENSION"},
            )
            dim.render()
        x_cursor = x_next

    # Diameter callouts for distinct intermediate diameters not covered by
    # max/head/shank dimensions.
    seen = {round(d, 2) for d in already_labeled_diameters if d and d > 0}
    x_dim = ox - DIM_OFFSET_LEFT - 11.0
    emitted = 0
    for seg in segments:
        for diameter in (seg.diameter_mm, seg.end_diameter_mm):
            if not diameter or diameter <= 0:
                continue
            rounded = round(diameter, 2)
            if any(abs(rounded - s) < 0.08 for s in seen):
                continue
            seen.add(rounded)
            radius = diameter / 2.0 * y_scale
            dim = msp.add_aligned_dim(
                p1=(x_dim - emitted * 8.0, oy - radius),
                p2=(x_dim - emitted * 8.0, oy + radius),
                distance=0,
                dimstyle="GB",
                text=f"%%C{diameter:g}",
                dxfattribs={"layer": "DIMENSION"},
            )
            dim.render()
            emitted += 1
            if emitted >= 3:
                return


def _draw_compact_process_title_block(
    msp: Any,
    frame: tuple[float, float, float, float],
    *,
    data: TitleBlock,
    machine_model: str,
) -> None:
    """Draw the sparse title block seen on factory process drawings."""
    _x0, y0, x1, _y1 = frame
    w = 180.0
    h = 30.0
    row_h = h / 3.0
    tb_x0 = x1 - w
    tb_y0 = y0
    tb_x1 = x1
    tb_y1 = y0 + h
    attribs = {"layer": "TITLEBLOCK", "lineweight": 35}

    msp.add_lwpolyline(
        [(tb_x0, tb_y0), (tb_x1, tb_y0), (tb_x1, tb_y1), (tb_x0, tb_y1)],
        close=True,
        dxfattribs=attribs,
    )
    mid_x = tb_x0 + 42.0
    msp.add_line((mid_x, tb_y0), (mid_x, tb_y1), dxfattribs={"layer": "TITLEBLOCK", "lineweight": 13})
    for i in range(1, 3):
        y = tb_y0 + i * row_h
        msp.add_line((tb_x0, y), (tb_x1, y), dxfattribs={"layer": "TITLEBLOCK", "lineweight": 13})

    rows = [
        ("单号", data.part_number or ""),
        ("机型", machine_model or "-"),
        ("产品名称", data.title or ""),
    ]
    for i, (label, value) in enumerate(rows):
        y_text = tb_y0 + i * row_h + row_h * 0.32
        msp.add_text(
            label,
            dxfattribs={
                "layer": "TITLEBLOCK",
                "style": "GB_CJK",
                "height": 3.0,
                "insert": (tb_x0 + 3.0, y_text),
            },
        )
        msp.add_text(
            value[:34],
            dxfattribs={
                "layer": "TITLEBLOCK",
                "style": "GB_CJK",
                "height": 3.2,
                "insert": (mid_x + 3.0, y_text),
            },
        )


def _infer_machine_model(*, case_id: str | None, forming: ProcessForming) -> str:
    """Best-effort extraction of 105S/106S/YT105S/Z46-8/3-style machine labels."""
    blob = " ".join([case_id or "", forming.part_name_zh or "", forming.material or ""])
    for pat in (r"\bYT\d{3}S\b", r"\b\d{3}S\b", r"\bZ\d+-\d+/\d+\b"):
        match = re.search(pat, blob, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return "-"


def _wrap_text(text: str, *, max_chars: int) -> list[str]:
    if not text:
        return []
    out, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= max_chars:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out
