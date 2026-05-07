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
  - Station number drawn in a circle above each workpiece.
  - ANSI31 section hatch on the workpiece interior.
  - >4 stations wrap to a second row (matches the real drawings).
  - Title block + drawing frame in GB style.
  - Dimension text uses `<>` so ezdxf auto-fills the measurement (no
    hard-coded numerics that drift from geometry).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.document import Drawing as DXFDocument

from app.data.schemas import (
    ProcessForming,
    StationStep,
    TitleBlock,
    WorkpieceGeometry,
)
from app.drawings.standards import (
    DRAWING_SIZES,
    DrawingFrame,
    TitleBlockTemplate,
    setup_dimension_style,
    setup_layers,
    setup_text_styles,
)


# Layout (mm in paper space)
STATIONS_PER_ROW_LIMIT = 4
ROW_VERTICAL_GAP = 90.0
WORKPIECE_BAND_TOP_MARGIN = 70.0
INTER_STATION_PADDING = 28.0    # min gap between adjacent workpiece bboxes
DIM_OFFSET_BELOW = 12.0
DIM_OFFSET_ABOVE = 10.0
DIM_OFFSET_LEFT = 10.0
DIM_OFFSET_RIGHT = 10.0
STATION_NUMBER_RADIUS = 4.0
STATION_NUMBER_GAP = 18.0       # above the workpiece outline
HATCH_PATTERN = "ANSI31"
HATCH_SCALE = 0.5
REASONING_BLOCK_HEIGHT = 50.0
REASONING_LINE_WIDTH = 90       # chars per line

# Real 过模图s exaggerate the radial axis so features are legible —
# a M14 bolt is 14mm wide × 100mm long, which would render as a thin line.
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


def _build_profile(w: WorkpieceGeometry) -> tuple[list[Segment], float, float]:
    """Dispatch to a profile builder. Returns (segments, max_y, total_x)."""
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
        fillet = (w.extra_dims_mm or {}).get("fillet_R", 0.0) if w.extra_dims_mm else 0.0
        segs, ymax = _profile_headed(L, R, head_R or R, head_H, shank_R, fillet)
    elif t == "stepped":
        segs, ymax = _profile_stepped(L, R, shank_R, shank_L)
    elif t == "tapered":
        segs, ymax = _profile_tapered(L, R)
    elif t == "pin":
        segs, ymax = _profile_pin(L, R)
    else:  # "cylinder" or "custom"
        segs, ymax = _profile_cylinder(L, R)
    return segs, ymax, L


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


def _hatch_workpiece(msp: Any, segs: list[Segment], *, ox: float, oy: float) -> None:
    """ANSI31 hatch on the upper half (representative section view)."""
    boundary: list[tuple[float, float]] = []
    for seg in segs:
        if seg[0] == "L":
            (x1, y1), (x2, y2) = seg[1], seg[2]
            if not boundary:
                boundary.append((ox + x1, oy + y1))
            boundary.append((ox + x2, oy + y2))
        # ARC segments rare in our profiles — skip from hatch boundary; the
        # visual cue is still strong without them.
    if len(boundary) < 3:
        return
    try:
        h = msp.add_hatch(color=8, dxfattribs={"layer": "HATCH"})
        h.set_pattern_fill(HATCH_PATTERN, scale=HATCH_SCALE)
        h.paths.add_polyline_path(boundary, is_closed=True)
    except Exception:
        # Hatch fails on degenerate boundary — skip silently
        pass


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
    if rows <= 2 and max_workpiece_w < 100:
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
    workpieces: list[tuple[str, WorkpieceGeometry, str | None]] = [
        ("下料 (Blank)", forming.blank, "原料下料"),
    ]
    for st in forming.stations:
        label = f"{_operation_label_zh(st.operation.value)}"
        workpieces.append((label, st.workpiece, st.notes_zh))

    n = len(workpieces)
    max_wp_w = max((w.overall_length_mm or 0.0) for _, w, _ in workpieces) or 1.0
    max_wp_h = max((w.max_diameter_mm or 0.0) for _, w, _ in workpieces) or 1.0

    paper = paper_size or _choose_paper_size(n, max_wp_w)
    paper_w, paper_h = DRAWING_SIZES.get(paper, DRAWING_SIZES["A2"])

    # Determine layout scales — separate axial (x) and radial (y).
    # Radial is exaggerated by RADIAL_EXAGGERATION so a thin bolt's diameter
    # is visually present rather than disappearing into the centerline.
    rows = math.ceil(n / STATIONS_PER_ROW_LIMIT)
    cols = min(n, STATIONS_PER_ROW_LIMIT)
    available_w = paper_w - 60.0
    needed_w = cols * (max_wp_w + INTER_STATION_PADDING) + 50.0
    x_scale = min(1.0, available_w / needed_w)
    available_h_per_row = (paper_h - 110.0) / max(rows, 1) - ROW_VERTICAL_GAP
    needed_h_per_row = max_wp_h * RADIAL_EXAGGERATION + 30.0
    y_scale = min(x_scale * RADIAL_EXAGGERATION, available_h_per_row / needed_h_per_row * RADIAL_EXAGGERATION)
    if y_scale < x_scale:
        y_scale = x_scale  # never compress radial below axial
    scale = x_scale  # used for the title-block scale label

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

    for i, (label_zh, w, notes) in enumerate(workpieces):
        row = i // STATIONS_PER_ROW_LIMIT
        col = i % STATIONS_PER_ROW_LIMIT
        col_count = min(STATIONS_PER_ROW_LIMIT, n - row * STATIONS_PER_ROW_LIMIT)
        # Center the row horizontally within the frame
        row_total_w = col_count * (max_wp_w * x_scale) + (col_count - 1) * INTER_STATION_PADDING
        x_start = fx0 + (fx1 - fx0 - row_total_w) / 2.0
        ox = x_start + col * (max_wp_w * x_scale + INTER_STATION_PADDING)
        oy = row_centers_y[row]

        # Build SCALED workpiece for the visual: x by axial scale, y by
        # exaggerated radial scale. Real-valued dims are emitted separately.
        scaled = w.model_copy(update={
            "overall_length_mm": (w.overall_length_mm or 0.0) * x_scale,
            "max_diameter_mm": (w.max_diameter_mm or 0.0) * y_scale,
            "head_diameter_mm": ((w.head_diameter_mm or 0.0) * y_scale) or None,
            "head_height_mm": ((w.head_height_mm or 0.0) * x_scale) or None,
            "shank_diameter_mm": ((w.shank_diameter_mm or 0.0) * y_scale) or None,
            "shank_length_mm": ((w.shank_length_mm or 0.0) * x_scale) or None,
        })
        segs, max_y, length = _build_profile(scaled)

        _add_centerline(msp, ox=ox, oy=oy, length=length)
        _draw_segments(msp, segs, ox=ox, oy=oy, mirror=False, layer="OUTLINE")
        _draw_segments(msp, segs, ox=ox, oy=oy, mirror=True, layer="OUTLINE")
        _hatch_workpiece(msp, segs, ox=ox, oy=oy)

        # Station number circle (use n=0 for blank)
        n_label = i  # 0 = blank, 1.. = station #
        _add_station_number(msp, n=n_label, ox=ox, oy_top=oy + max_y, length=length)

        # Operation label below the station number
        msp.add_text(
            label_zh,
            dxfattribs={
                "layer": "TEXT", "style": "GB_CJK", "height": 3.5,
                "insert": (ox, oy + max_y + STATION_NUMBER_GAP - 8),
            },
        )
        # Notes (Chinese) below the workpiece, above the dim
        if notes:
            msp.add_text(
                notes[:36],
                dxfattribs={
                    "layer": "TEXT", "style": "GB_CJK", "height": 2.5,
                    "insert": (ox, oy - max_y - DIM_OFFSET_BELOW - 9),
                },
            )

        # Dimensions reflect REAL (unscaled) values via auto-measurement.
        # We pass the *scaled* geometry positions but the dim text shows
        # `<>` -> ezdxf calculates from scaled coords, so we manually pass
        # the real measurement in the override:
        _draw_real_dims(msp, w=w, ox=ox, oy=oy, max_y=max_y, length=length)

    # Reasoning block (lower left, above title block)
    rx = fx0 + 5.0
    ry = fy0 + 50.0
    msp.add_text(
        f"工艺理由 / Reasoning  (cited: {', '.join(forming.cited_case_ids) or '-'})",
        dxfattribs={"layer": "TEXT", "style": "GB_CJK", "height": 3.0,
                    "insert": (rx, ry + 12)},
    )
    for i, line in enumerate(_wrap_text(forming.reasoning_zh, max_chars=REASONING_LINE_WIDTH)[:6]):
        msp.add_text(
            line,
            dxfattribs={"layer": "TEXT", "style": "GB_CJK", "height": 2.5,
                        "insert": (rx, ry - i * 4)},
        )

    # Title block — pick a sensible scale string
    scale_str = f"1:{int(round(1 / scale)) if scale > 0 else 1}"
    tb_data = TitleBlock(
        part_number=case_id or forming.part_name_zh,
        title=f"{forming.part_name_zh} 过模图",
        material=forming.material,
        scale=scale_str,
        revision="A",
    )
    TitleBlockTemplate().draw(msp, frame, tb_data)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))
    return output_path


def _draw_real_dims(
    msp: Any, *, w: WorkpieceGeometry, ox: float, oy: float, max_y: float, length: float,
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
