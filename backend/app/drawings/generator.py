"""
2D drawing generator using ezdxf.

Generates engineering drawings from structured parameters:
- Die component drawings (punch + die) with real DIMENSION entities and ANSI31 hatch
- Production drawings with dimension chains and tolerances
- Process breakdown sheets showing intermediate workpiece shapes

Output: DXF files following GB/T 4458 mechanical drawing standards.
Each dimension must call .render() or geometry won't appear in AutoCAD/LibreCAD.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import ezdxf

from app.core.logging import get_logger
from app.data.schemas import (
    DieComponentParams,
    DieGeometryType,
    DieParameters,
    PartFeatures,
    ProcessPlan,
)
from app.drawings.standards import (
    DrawingFrame,
    TitleBlockTemplate,
    setup_dimension_style,
    setup_layers,
    setup_text_styles,
)
from app.geometry.profiles import (
    build_die_wall,
    build_punch_profile,
    die_dimensions,
    die_kind,
    punch_dimensions,
    punch_face_kind,
)

logger = get_logger(__name__)

_OL = {"layer": "OUTLINE", "lineweight": 50}
_CTR = {"layer": "CENTER", "lineweight": 25}
_HID = {"layer": "HIDDEN", "lineweight": 25}
_ANN = {"layer": "ANNOTATION", "height": 3.5, "style": "GB_NOTE"}
_TXT = {"layer": "TEXT", "height": 3.0, "style": "GB_NOTE"}


class DrawingGenerator:
    """Generate DXF engineering drawings from structured die parameters."""

    def __init__(self, dxf_version: str = "R2018") -> None:
        self._dxf_version = dxf_version
        self._frame = DrawingFrame()
        self._title_block = TitleBlockTemplate()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_die_drawing(
        self,
        die_params: DieComponentParams,
        station_number: int,
        output_path: str | Path,
        paper_size: str = "A3",
    ) -> Path:
        """Generate a die component drawing (punch or die insert)."""
        output_path = Path(output_path)
        component = die_params.component_type

        doc = ezdxf.new(self._dxf_version)
        setup_layers(doc)
        setup_text_styles(doc)
        setup_dimension_style(doc)
        msp = doc.modelspace()

        frame_coords = self._frame.draw(msp, paper_size)
        x0, y0, x1, y1 = frame_coords

        # Compute fit-to-page scale
        shoulder_r = (die_params.shoulder_diameter
                      or die_params.outer_diameter * 1.35) / 2
        total_len = die_params.working_length + min(
            die_params.working_length * 0.25, 18.0
        )
        layout = _view_layout(
            area=(x0, y0 + 50, x1 - 5, y1 - 5),
            side_extent=(total_len, max(shoulder_r * 2, die_params.outer_diameter)),
            has_end_view=True,
        )
        scale = layout["scale"]
        side_cx, side_cy = layout["side_origin"]
        end_cx, end_cy = layout["end_origin"]

        from app.data.schemas import TitleBlock
        title_data = TitleBlock(
            title=f"Station {station_number} — {component.title()} Drawing",
            material=die_params.material,
            scale=layout["scale_label"],
        )
        self._title_block.draw(msp, frame_coords, title_data)

        if component == "punch":
            self._draw_punch_view(msp, die_params, side_cx, side_cy, scale)
            self._draw_punch_end_view(msp, die_params, end_cx, end_cy, scale)
        else:
            self._draw_die_view(msp, die_params, side_cx, side_cy, scale)
            self._draw_die_end_view(msp, die_params, end_cx, end_cy, scale)

        # Section view labels (A-A on side view, "View A" callout on end view)
        msp.add_text(
            "A-A", dxfattribs={**_ANN, "insert": (side_cx - 4, side_cy + total_len * scale + 6), "height": 4.5}
        )
        msp.add_text(
            "View A", dxfattribs={**_ANN, "insert": (end_cx - 8, end_cy + die_params.outer_diameter / 2 * scale + 6), "height": 4.5}
        )

        self._add_material_notes(msp, die_params, x0 + 5, y0 + 50)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(output_path))
        logger.info("die_drawing_generated", path=str(output_path), component=component)
        return output_path

    def generate_production_drawing(
        self,
        part_features: PartFeatures,
        process_plan: ProcessPlan,
        output_path: str | Path,
        paper_size: str = "A3",
    ) -> Path:
        """Generate production drawing with finished part dimensions."""
        output_path = Path(output_path)
        doc = ezdxf.new(self._dxf_version)
        setup_layers(doc)
        setup_text_styles(doc)
        setup_dimension_style(doc)
        msp = doc.modelspace()

        frame_coords = self._frame.draw(msp, paper_size)
        x0, y0, x1, y1 = frame_coords

        # Compute fit-to-page layout
        layout = _view_layout(
            area=(x0, y0 + 50, x1 - 5, y1 - 5),
            side_extent=(part_features.overall_length, part_features.head.diameter),
            has_end_view=True,
        )
        scale = layout["scale"]
        side_cx, side_cy = layout["side_origin"]
        top_cx, top_cy = layout["end_origin"]

        from app.data.schemas import TitleBlock
        title_data = TitleBlock(
            part_number=part_features.part_number,
            title=part_features.description,
            material=part_features.material_grade,
            scale=layout["scale_label"],
            standard=part_features.standard,
        )
        self._title_block.draw(msp, frame_coords, title_data)

        self._draw_fastener_profile(msp, part_features, side_cx, side_cy, scale)
        self._add_part_dimensions(msp, part_features, side_cx, side_cy, scale)
        self._draw_fastener_top_view(msp, part_features, top_cx, top_cy, scale)

        # Zoomed drive-recess detail (~3x actual size) tucked above title block.
        drive = part_features.head.drive_type.value
        if drive != "none" and part_features.head.drive_size:
            self._draw_drive_recess_detail(
                msp,
                features=part_features,
                cx=x1 - 30,
                cy=y0 + 60,
                zoom=3.0,
            )

        # Production / performance text panels
        self._add_production_notes(msp, part_features, process_plan, x0 + 5, y1 - 10)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(output_path))
        logger.info("production_drawing_generated", path=str(output_path))
        return output_path

    def generate_process_breakdown(
        self,
        process_plan: ProcessPlan,
        output_path: str | Path,
        paper_size: str = "A3",
    ) -> Path:
        """Generate process breakdown sheet showing intermediate shapes."""
        output_path = Path(output_path)
        doc = ezdxf.new(self._dxf_version)
        setup_layers(doc)
        setup_text_styles(doc)
        msp = doc.modelspace()

        frame_coords = self._frame.draw(msp, paper_size)
        x0, y0, x1, y1 = frame_coords

        from app.data.schemas import TitleBlock
        title_data = TitleBlock(title="Process Breakdown Sheet", scale="1:1")
        self._title_block.draw(msp, frame_coords, title_data)

        n = process_plan.total_stations + 1
        spacing = (x1 - x0 - 40) / max(n, 1)
        shapes = [process_plan.stations[0].input_shape] + [
            s.output_shape for s in process_plan.stations
        ]
        ops = ["Blank"] + [s.operation.value.replace("_", " ").title() for s in process_plan.stations]

        for i, (shape, op_name) in enumerate(zip(shapes, ops)):
            cx = x0 + 20 + spacing * (i + 0.5)
            cy = y0 + (y1 - y0) * 0.50
            self._draw_workpiece_silhouette(msp, shape, cx, cy, op_name, i)

            # Arrow between shapes
            if i < len(shapes) - 1:
                ax_start = cx + shape.max_diameter / 2 * _fit_scale(shape) + 3
                ax_end = cx + spacing - shape.max_diameter / 2 * _fit_scale(shape) - 3
                if ax_end > ax_start:
                    msp.add_line(
                        (ax_start, cy), (ax_end, cy),
                        dxfattribs={"layer": "DIMENSION"},
                    )
                    msp.add_line(
                        (ax_end, cy), (ax_end - 4, cy + 2),
                        dxfattribs={"layer": "DIMENSION"},
                    )
                    msp.add_line(
                        (ax_end, cy), (ax_end - 4, cy - 2),
                        dxfattribs={"layer": "DIMENSION"},
                    )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(output_path))
        logger.info("process_breakdown_generated", path=str(output_path))
        return output_path

    # ------------------------------------------------------------------
    # Punch drawing
    # ------------------------------------------------------------------

    def _draw_punch_view(
        self,
        msp: Any,
        params: DieComponentParams,
        cx: float,
        cy: float,
        scale: float = 1.0,
    ) -> None:
        """
        Draw punch as a front sectional view at the given scale.

        Profile geometry comes from app.geometry.profiles.build_punch_profile so
        the 2D drawing and the revolved 3D mesh share a single source of truth.
        Right half is hatched; left half is outline only.
        """
        d = punch_dimensions(params)
        od_r = d["od_r"]
        wd_r = d["wd_r"]
        sd_r = d["sd_r"]
        total_len = d["total"]
        body_len = d["body_len"]
        shoulder_len = d["shoulder_len"]
        face_kind = punch_face_kind(params)
        approach = params.approach_angle_deg
        land_len = params.land_length or 0.0

        profile_rw = build_punch_profile(params)

        def S(r: float, z: float) -> tuple[float, float]:
            return (cx + r * scale, cy + z * scale)

        pts_right = [S(r, z) for r, z in profile_rw]
        self._add_hatch(msp, pts_right)
        msp.add_lwpolyline(pts_right, close=True, dxfattribs=_OL)
        pts_left = [(2 * cx - x, y) for x, y in pts_right]
        msp.add_lwpolyline(pts_left, close=True, dxfattribs=_OL)

        # Center line through the axis.
        total_len_s = total_len * scale
        msp.add_line((cx, cy - 8), (cx, cy + total_len_s + 8), dxfattribs=_CTR)

        # --- Dimensions ---
        od_s = od_r * scale
        shoulder_s = sd_r * scale
        body_len_s = body_len * scale
        dim_h_off = max(od_s + 14, 18)
        dim_v_off = max(shoulder_s + 14, 18)

        # Body ⌀ (with h7-style tolerance band — engineers expect ⁰/₋)
        self._add_linear_dim(
            msp,
            p1=S(-od_r, shoulder_len + body_len * 0.5),
            p2=S( od_r, shoulder_len + body_len * 0.5),
            base=(cx, cy - dim_h_off),
            angle=0,
            text=f"⌀{params.outer_diameter:.3f} 0/-0.013",
        )

        # Shoulder ⌀ (always present — used for retention)
        if abs(sd_r - od_r) > 0.05:
            self._add_linear_dim(
                msp,
                p1=S(-sd_r, shoulder_len * 0.5),
                p2=S( sd_r, shoulder_len * 0.5),
                base=(cx, cy - dim_h_off - 14),
                angle=0,
                text=f"⌀{sd_r * 2:.1f}",
            )

        # Body length (vertical)
        self._add_linear_dim(
            msp,
            p1=S(od_r, shoulder_len),
            p2=S(od_r, total_len),
            base=(cx + dim_v_off, cy + (shoulder_len + body_len_s / 2 / scale) * scale),
            angle=90,
            text=f"{body_len:.1f}",
        )

        # Total length (vertical, outer)
        self._add_linear_dim(
            msp,
            p1=S(sd_r, 0),
            p2=S(sd_r, total_len),
            base=(cx + dim_v_off + 14, cy + total_len_s / 2),
            angle=90,
            text=f"{total_len:.1f}",
        )

        # --- Working face feature callout ---
        if face_kind == "sphere":
            # Sphere R is the body OD radius (full hemisphere on top of body).
            sx, sy = S(od_r * 0.6, total_len - od_r * 0.4)
            msp.add_text(
                f"SR{od_r:.2f}",
                dxfattribs={**_ANN, "insert": (sx + 4, sy + 4)},
            )
        elif face_kind == "countersink" and approach:
            ang_x, ang_y = S(od_r * 0.5, total_len - 2.0)
            msp.add_text(
                f"{approach:.0f}° head",
                dxfattribs={**_ANN, "insert": (ang_x + 3, ang_y - 2)},
            )
        elif face_kind == "extrusion" and land_len > 0:
            # Working tip ⌀ + land length
            self._add_linear_dim(
                msp,
                p1=S(-wd_r, total_len - land_len * 0.5),
                p2=S( wd_r, total_len - land_len * 0.5),
                base=(cx, cy + total_len_s + 12),
                angle=0,
                text=f"⌀{wd_r * 2:.2f}",
            )
            self._add_linear_dim(
                msp,
                p1=S(-od_r, total_len - land_len),
                p2=S(-od_r, total_len),
                base=(cx - dim_v_off, cy + (total_len - land_len / 2) * scale),
                angle=90,
                text=f"land {land_len:.1f}",
            )
            if approach:
                ang_x, ang_y = S(od_r * 0.6, total_len - land_len - 2.0)
                msp.add_text(
                    f"{approach:.0f}° approach",
                    dxfattribs={**_ANN, "insert": (ang_x + 3, ang_y)},
                )

        # Entry radius callout (under-shoulder fillet hint)
        if params.entry_radius and params.entry_radius > 0:
            ax, ay = S(od_r, shoulder_len + 1.0)
            msp.add_line((ax + 6, ay - 6), (ax + 14, ay - 14), dxfattribs={"layer": "ANNOTATION"})
            msp.add_text(
                f"R{params.entry_radius:.2f}",
                dxfattribs={**_ANN, "insert": (ax + 14, ay - 14)},
            )

        # Surface-finish ▽ symbol on working face — leader line points at the
        # tip of the punch so the symbol is unambiguously tied to that surface.
        sra = params.surface_roughness_ra
        ra_text_x = cx + od_s + 8
        ra_text_y = cy + total_len_s - 6
        msp.add_line(
            (cx + wd_r * scale, ra_text_y),
            (ra_text_x - 1, ra_text_y),
            dxfattribs={"layer": "ANNOTATION"},
        )
        msp.add_text(
            f"Ra {sra:.1f}  ▽▽▽",
            dxfattribs={**_ANN, "insert": (ra_text_x, ra_text_y)},
        )

    # ------------------------------------------------------------------
    # End view (looking along the punch axis)
    # ------------------------------------------------------------------

    def _draw_punch_end_view(
        self,
        msp: Any,
        params: DieComponentParams,
        cx: float,
        cy: float,
        scale: float,
    ) -> None:
        """End view of punch — concentric circles for OD and shoulder."""
        od_s = params.outer_diameter / 2 * scale
        shoulder_s = (params.shoulder_diameter or params.outer_diameter * 1.35) / 2 * scale

        # Outer (shoulder) silhouette as hidden if smaller, else outline
        if shoulder_s > od_s + 0.5:
            msp.add_circle((cx, cy), shoulder_s, dxfattribs=_HID)
        # Working OD
        msp.add_circle((cx, cy), od_s, dxfattribs=_OL)

        # Center cross (extends slightly beyond)
        ext = max(od_s, shoulder_s) + 4
        msp.add_line((cx - ext, cy), (cx + ext, cy), dxfattribs=_CTR)
        msp.add_line((cx, cy - ext), (cx, cy + ext), dxfattribs=_CTR)

        # ⌀OD dimension (horizontal across the circle)
        self._add_linear_dim(
            msp,
            p1=(cx - od_s, cy),
            p2=(cx + od_s, cy),
            base=(cx, cy - ext - 8),
            angle=0,
            text=f"⌀{params.outer_diameter:.3f}",
        )

    # ------------------------------------------------------------------
    # Die drawing
    # ------------------------------------------------------------------

    def _draw_die_view(
        self,
        msp: Any,
        params: DieComponentParams,
        cx: float,
        cy: float,
        scale: float = 1.0,
    ) -> None:
        """
        Draw die as a full sectional view at the given scale.

        Wall cross-section is a closed polygon from build_die_wall — the same
        polygon is revolved to make the 3D mesh, so 2D and 3D cannot drift.
        Right half is hatched (wall material visible); left half mirrors.
        """
        d = die_dimensions(params)
        od_r = d["od_r"]
        id_r = d["id_r"]
        length = d["total"]
        kind = die_kind(params)
        approach = params.approach_angle_deg
        clearance = getattr(params, "clearance_mm", None) or id_r * 0.003

        wall_rw = build_die_wall(params)

        def S(r: float, z: float) -> tuple[float, float]:
            return (cx + r * scale, cy + z * scale)

        pts_right = [S(r, z) for r, z in wall_rw]
        self._add_hatch(msp, pts_right)
        msp.add_lwpolyline(pts_right, close=True, dxfattribs=_OL)
        pts_left = [(2 * cx - x, y) for x, y in pts_right]
        msp.add_lwpolyline(pts_left, close=True, dxfattribs=_OL)

        # Center line through the axis.
        top_s = length * scale
        msp.add_line((cx, cy - 8), (cx, cy + top_s + 8), dxfattribs=_CTR)

        # --- Dimensions ---
        od_s = od_r * scale
        dim_h_off = max(od_s + 14, 18)
        dim_v_off = max(od_s + 14, 18)

        # OD
        self._add_linear_dim(
            msp,
            p1=S(-od_r, -1),
            p2=S( od_r, -1),
            base=(cx, cy - dim_h_off),
            angle=0,
            text=f"⌀{params.outer_diameter:.1f}",
        )

        # Bore ID with tolerance
        tol_upper = round(clearance * 2, 3)
        bore_id = params.inner_diameter or od_r * 0.6
        self._add_linear_dim(
            msp,
            p1=S(-id_r, length * 0.5),
            p2=S( id_r, length * 0.5),
            base=(cx, cy - dim_h_off - 14),
            angle=0,
            text=f"⌀{bore_id:.3f}  +{tol_upper:.3f}/0",
        )

        # Total length
        self._add_linear_dim(
            msp,
            p1=S(od_r, 0),
            p2=S(od_r, length),
            base=(cx + dim_v_off, cy + top_s / 2),
            angle=90,
            text=f"{length:.1f}",
        )

        # --- Zone labels per archetype ---
        if kind == "extrusion_3zone":
            land = d["land"]
            relief_h = max(0.5, min(length * 0.20, 6.0))
            z_land_bot = relief_h
            z_land_top = z_land_bot + land
            if z_land_top > length - d["entry_chamfer"] - 0.5:
                z_land_top = length - d["entry_chamfer"] - 0.5
            # Entry / Land / Relief labels on the LEFT side of the view.
            label_x = cx - od_s - 6
            for label, z_mid in [
                ("Entry",  (z_land_top + length) / 2),
                ("Land",   (z_land_bot + z_land_top) / 2),
                ("Relief", z_land_bot / 2),
            ]:
                msp.add_text(
                    label,
                    dxfattribs={**_ANN, "insert": (label_x, cy + z_mid * scale - 1.5)},
                )
            # Land length dimension on the left.
            self._add_linear_dim(
                msp,
                p1=S(-od_r, z_land_bot),
                p2=S(-od_r, z_land_top),
                base=(cx - dim_v_off - 6, cy + (z_land_bot + z_land_top) / 2 * scale),
                angle=90,
                text=f"land {land:.1f}",
            )
            if approach:
                ang_x, ang_y = S(od_r * 0.4, z_land_top + 1.0)
                msp.add_text(
                    f"approach {approach:.0f}°",
                    dxfattribs={**_ANN, "insert": (ang_x + 3, ang_y)},
                )
            if params.relief_angle_deg:
                rx, ry = S(od_r * 0.4, relief_h * 0.4)
                msp.add_text(
                    f"relief {params.relief_angle_deg:.0f}°",
                    dxfattribs={**_ANN, "insert": (rx + 3, ry)},
                )
        elif kind in ("closed_heading", "flat_face"):
            cavity_d = d["cavity_depth"] or length * 0.40
            cavity_d = min(cavity_d, length * 0.6)
            cavity_r = d["cavity_radius"]
            z_cavity_bot = length - cavity_d
            # Cavity DEPTH (vertical, on left).
            self._add_linear_dim(
                msp,
                p1=S(-od_r, z_cavity_bot),
                p2=S(-od_r, length),
                base=(cx - dim_v_off, cy + (length - cavity_d / 2) * scale),
                angle=90,
                text=f"cavity D {cavity_d:.1f}",
            )
            # Cavity DIAMETER (horizontal, above the part).
            self._add_linear_dim(
                msp,
                p1=S(-cavity_r, length - cavity_d * 0.4),
                p2=S( cavity_r, length - cavity_d * 0.4),
                base=(cx, cy + top_s + 14),
                angle=0,
                text=f"⌀{cavity_r * 2:.2f}",
            )
            # Through-bore length below the cavity.
            self._add_linear_dim(
                msp,
                p1=S(-od_r, 0),
                p2=S(-od_r, z_cavity_bot),
                base=(cx - dim_v_off - 14, cy + z_cavity_bot / 2 * scale),
                angle=90,
                text=f"bore {z_cavity_bot:.1f}",
            )
            # "Heading cavity" / "Flat-head pocket" label, pushed past dim text
            # so it does not overlap with the total-length dimension.
            label = "Heading cavity" if kind == "closed_heading" else "Flat-head pocket"
            label_x = cx + dim_v_off + 12
            label_y = cy + (length - cavity_d / 2) * scale
            msp.add_text(
                label,
                dxfattribs={**_ANN, "insert": (label_x, label_y)},
            )
            # Leader from label towards the cavity wall.
            msp.add_line(
                (label_x - 1, label_y + 1),
                (cx + cavity_r * scale + 1, label_y + 1),
                dxfattribs={"layer": "ANNOTATION"},
            )

        # Entry radius / chamfer callout
        if params.entry_radius and params.entry_radius > 0:
            rx, ry = S(id_r, length)
            msp.add_text(
                f"R{params.entry_radius:.2f}",
                dxfattribs={**_ANN, "insert": (rx + 3, ry + 3)},
            )

        # Surface-finish ▽ symbol on bore wall — anchored with a leader line so
        # it points at the actual surface it qualifies (not floating mid-air).
        sra = params.surface_roughness_ra
        ra_text_x = cx + od_s + 8
        ra_text_y = cy + top_s * 0.45
        bore_x = cx + id_r * scale
        msp.add_line(
            (bore_x, ra_text_y),
            (ra_text_x - 1, ra_text_y),
            dxfattribs={"layer": "ANNOTATION"},
        )
        msp.add_text(
            f"Ra {sra:.1f}  ▽▽▽",
            dxfattribs={**_ANN, "insert": (ra_text_x, ra_text_y)},
        )

    # ------------------------------------------------------------------
    # Die end view (looking down through bore)
    # ------------------------------------------------------------------

    def _draw_die_end_view(
        self,
        msp: Any,
        params: DieComponentParams,
        cx: float,
        cy: float,
        scale: float,
    ) -> None:
        """Concentric circles: OD body (with hatched ring) + bore."""
        od_s = params.outer_diameter / 2 * scale
        id_s = (params.inner_diameter or params.outer_diameter * 0.3) / 2 * scale

        # Hatch the annular wall (between bore and OD) using a polyline ring
        # Approximated as 32-segment poly for both circles.
        ring_outer: list[tuple[float, float]] = []
        ring_inner: list[tuple[float, float]] = []
        for i in range(32):
            a = 2 * math.pi * i / 32
            ring_outer.append((cx + od_s * math.cos(a), cy + od_s * math.sin(a)))
            ring_inner.append((cx + id_s * math.cos(a), cy + id_s * math.sin(a)))

        try:
            hatch = msp.add_hatch(color=8, dxfattribs={"layer": "HATCH"})
            hatch.set_pattern_fill("ANSI31", scale=1.5, angle=45)
            hatch.paths.add_polyline_path(ring_outer + [ring_outer[0]], is_closed=True)
            hatch.paths.add_polyline_path(ring_inner + [ring_inner[0]], is_closed=True, flags=0)
        except Exception as exc:
            logger.debug("die_end_hatch_failed", error=str(exc))

        msp.add_circle((cx, cy), od_s, dxfattribs=_OL)
        msp.add_circle((cx, cy), id_s, dxfattribs=_OL)

        # Center cross
        ext = od_s + 4
        msp.add_line((cx - ext, cy), (cx + ext, cy), dxfattribs=_CTR)
        msp.add_line((cx, cy - ext), (cx, cy + ext), dxfattribs=_CTR)

        # A-A cutting-plane indicator: short heavy stubs at each end of the
        # horizontal centerline, with arrow heads pointing inward. This pairs
        # with the "A-A" label on the side view so engineers can locate the
        # section. (Per GB/T 17452 / ISO 128, the cut runs through the bore.)
        stub = 4.0
        for sign in (-1, 1):
            anchor_x = cx + sign * (ext + 1)
            msp.add_line(
                (anchor_x, cy - stub), (anchor_x, cy + stub),
                dxfattribs={**_OL, "lineweight": 70},
            )
            msp.add_text(
                "A",
                dxfattribs={**_ANN, "insert": (anchor_x + sign * 1.5 - 1.5, cy + stub + 1)},
            )
            # Arrow tick pointing toward the part centerline.
            msp.add_line(
                (anchor_x, cy),
                (anchor_x - sign * 3, cy + 1.5),
                dxfattribs={"layer": "DIMENSION"},
            )
            msp.add_line(
                (anchor_x, cy),
                (anchor_x - sign * 3, cy - 1.5),
                dxfattribs={"layer": "DIMENSION"},
            )

        # Diameters
        self._add_linear_dim(
            msp,
            p1=(cx - od_s, cy),
            p2=(cx + od_s, cy),
            base=(cx, cy - ext - 8),
            angle=0,
            text=f"⌀{params.outer_diameter:.1f}",
        )
        if params.inner_diameter:
            self._add_linear_dim(
                msp,
                p1=(cx - id_s, cy + 0.5),
                p2=(cx + id_s, cy + 0.5),
                base=(cx, cy + ext + 8),
                angle=0,
                text=f"⌀{params.inner_diameter:.3f}",
            )

    # ------------------------------------------------------------------
    # Fastener profile (production drawing)
    # ------------------------------------------------------------------

    def _draw_fastener_profile(
        self,
        msp: Any,
        features: PartFeatures,
        cx: float,
        cy: float,
        scale: float = 1.0,
    ) -> None:
        """Draw a half-section view of the finished fastener at the given scale."""
        head_r = features.head.diameter / 2
        shank_r = features.shank.diameter / 2
        head_h = features.head.height
        shank_len = features.shank.length
        thread_len = features.thread.length
        thread_r = features.thread.nominal_diameter / 2
        underhead_r = features.head.underhead_radius or 0.0

        # Build profile in real-world (radial, axial). Origin = thread tip,
        # head at top.
        profile_rw: list[tuple[float, float]] = []

        # Tail / tip
        profile_rw.append((0.0, 0.0))
        if features.tail and features.tail.type.value == "pointed" and features.tail.length:
            profile_rw.append((thread_r, features.tail.length))
            tail_z = features.tail.length
        else:
            profile_rw.append((thread_r, 0.0))
            tail_z = 0.0

        # Threaded section
        thread_top_z = tail_z + thread_len
        profile_rw.append((thread_r, thread_top_z))

        # Smooth shank
        shank_top_z = thread_top_z + shank_len
        if shank_len > 0:
            profile_rw.append((shank_r, thread_top_z))
            profile_rw.append((shank_r, shank_top_z))
        else:
            shank_top_z = thread_top_z

        # Under-head fillet (approximated as two segments)
        head_bottom_z = shank_top_z
        if underhead_r > 0:
            profile_rw.append((shank_r + underhead_r, head_bottom_z))
            head_bottom_z += underhead_r * 0.7
            profile_rw.append((head_r, head_bottom_z))
        else:
            profile_rw.append((head_r, head_bottom_z))

        # Head body (with optional countersink chamfer)
        if features.head.type.value == "flat" and features.head.chamfer_angle_deg:
            chamfer_dz = head_h
            profile_rw.append((shank_r + 0.2, head_bottom_z))  # cut-back for chamfer line
            profile_rw.append((head_r, head_bottom_z + chamfer_dz))
        else:
            profile_rw.append((head_r, head_bottom_z + head_h))

        profile_rw.append((0.0, head_bottom_z + head_h))
        total_len = head_bottom_z + head_h

        def S(r: float, z: float) -> tuple[float, float]:
            return (cx + r * scale, cy + z * scale)

        pts_right = [S(r, z) for r, z in profile_rw]
        self._add_hatch(msp, pts_right)
        msp.add_lwpolyline(pts_right, close=True, dxfattribs=_OL)
        pts_left = [(2 * cx - x, y) for x, y in pts_right]
        msp.add_lwpolyline(pts_left, close=True, dxfattribs=_OL)

        # Thread representation — short crests on the threaded section
        if thread_len * scale > 4:
            pitch_s = max(features.thread.pitch * scale, 1.5)
            z = tail_z + pitch_s
            r_s = thread_r * scale
            while z < thread_top_z - pitch_s * 0.5:
                yy = cy + z * scale
                msp.add_line(
                    (cx - r_s * 0.94, yy), (cx + r_s * 0.94, yy),
                    dxfattribs={"layer": "HIDDEN", "lineweight": 13},
                )
                z += pitch_s

        # Center line
        msp.add_line(
            (cx, cy - 6), (cx, cy + total_len * scale + 6),
            dxfattribs=_CTR,
        )

    def _add_part_dimensions(
        self,
        msp: Any,
        features: PartFeatures,
        cx: float,
        cy: float,
        scale: float = 1.0,
    ) -> None:
        """Add DIMENSION entities for the production drawing at given scale."""
        head_r = features.head.diameter / 2
        shank_r = features.shank.diameter / 2
        thread_r = features.thread.nominal_diameter / 2
        head_h = features.head.height
        shank_len = features.shank.length
        thread_len = features.thread.length

        tail_z = (features.tail.length if features.tail and features.tail.length else 0.0)
        thread_top = tail_z + thread_len
        shank_top = thread_top + shank_len
        head_bot = shank_top + (features.head.underhead_radius or 0.0) * 0.7
        head_top = head_bot + head_h

        def S(r: float, z: float) -> tuple[float, float]:
            return (cx + r * scale, cy + z * scale)

        head_r_s = head_r * scale
        head_top_s = head_top * scale

        # --- Diameters (stacked below the part) ---
        dim_h0 = max(head_r_s + 14, 18)

        # Thread major ⌀ + spec
        self._add_linear_dim(
            msp,
            p1=S(-thread_r, tail_z + thread_len * 0.4),
            p2=S( thread_r, tail_z + thread_len * 0.4),
            base=(cx, cy - dim_h0),
            angle=0,
            text=features.thread.spec,
        )

        # Shank ⌀ (only if shank length > 0)
        if shank_len > 0:
            self._add_linear_dim(
                msp,
                p1=S(-shank_r, thread_top + shank_len * 0.5),
                p2=S( shank_r, thread_top + shank_len * 0.5),
                base=(cx, cy - dim_h0 - 14),
                angle=0,
                text=f"⌀{features.shank.diameter:.2f}",
            )

        # Head ⌀
        self._add_linear_dim(
            msp,
            p1=S(-head_r, head_bot + head_h * 0.5),
            p2=S( head_r, head_bot + head_h * 0.5),
            base=(cx, cy - dim_h0 - 28),
            angle=0,
            text=f"⌀{features.head.diameter:.2f}",
        )

        # --- Lengths (stacked to the right) ---
        dim_v0 = head_r_s + 14

        # Overall length
        self._add_linear_dim(
            msp,
            p1=S(head_r, 0),
            p2=S(head_r, head_top),
            base=(cx + dim_v0, cy + head_top_s / 2),
            angle=90,
            text=f"L={features.overall_length:.1f}",
        )

        # Thread length
        self._add_linear_dim(
            msp,
            p1=S(thread_r, tail_z),
            p2=S(thread_r, thread_top),
            base=(cx + dim_v0 + 16, cy + (tail_z + thread_top) * scale / 2),
            angle=90,
            text=f"thd {thread_len:.1f}",
        )

        # Head height
        self._add_linear_dim(
            msp,
            p1=S(head_r + 0.5, head_bot),
            p2=S(head_r + 0.5, head_top),
            base=(cx + dim_v0 + 32, cy + (head_bot + head_h / 2) * scale),
            angle=90,
            text=f"h={features.head.height:.1f}",
        )

        # Shank length (if any)
        if shank_len > 0:
            self._add_linear_dim(
                msp,
                p1=S(shank_r, thread_top),
                p2=S(shank_r, shank_top),
                base=(cx + dim_v0 + 48, cy + (thread_top + shank_len / 2) * scale),
                angle=90,
                text=f"shank {shank_len:.1f}",
            )

        # --- Feature callouts (radii, chamfer, drive) ---
        # Under-head fillet
        if features.head.underhead_radius:
            ax, ay = S(shank_r, shank_top)
            msp.add_text(
                f"R{features.head.underhead_radius:.2f}",
                dxfattribs={**_ANN, "insert": (ax + 4, ay)},
            )

        # Countersink / chamfer angle for flat heads
        if features.head.type.value == "flat" and features.head.chamfer_angle_deg:
            cx_text = cx - head_r_s - 30
            msp.add_text(
                f"{features.head.chamfer_angle_deg:.0f}° C'sink",
                dxfattribs={**_ANN, "insert": (cx_text, cy + (head_bot + head_h * 0.5) * scale)},
            )

        # Drive recess callout
        drive = features.head.drive_type.value
        drive_size = features.head.drive_size
        if drive != "none" and drive_size:
            label = {
                "hex_socket": f"Hex {drive_size:.1f}",
                "torx": f"Torx T{int(drive_size)}",
                "cross": f"Cross #{int(drive_size)}",
                "slotted": f"Slot {drive_size:.1f}",
            }.get(drive, f"{drive} {drive_size}")
            msp.add_text(
                label,
                dxfattribs={**_ANN, "insert": (cx + head_r_s + 4, cy + head_top_s - 2)},
            )

    # ------------------------------------------------------------------
    # Top view (looking down at head, showing drive recess)
    # ------------------------------------------------------------------

    def _draw_fastener_top_view(
        self,
        msp: Any,
        features: PartFeatures,
        cx: float,
        cy: float,
        scale: float,
    ) -> None:
        """Top view of the head: outer circle + drive recess."""
        head_r_s = features.head.diameter / 2 * scale
        shank_r_s = features.shank.diameter / 2 * scale

        # Head outline + (lighter) shank shadow
        msp.add_circle((cx, cy), head_r_s, dxfattribs=_OL)
        if shank_r_s < head_r_s - 0.5:
            msp.add_circle((cx, cy), shank_r_s, dxfattribs=_HID)

        # Center cross
        ext = head_r_s + 4
        msp.add_line((cx - ext, cy), (cx + ext, cy), dxfattribs=_CTR)
        msp.add_line((cx, cy - ext), (cx, cy + ext), dxfattribs=_CTR)

        # Drive recess
        drive = features.head.drive_type.value
        drive_size = features.head.drive_size
        if drive != "none" and drive_size:
            self._draw_drive_recess(
                msp, cx, cy, drive, drive_size, scale,
                head_r_mm=features.head.diameter / 2,
            )

        # Head ⌀ dimension
        self._add_linear_dim(
            msp,
            p1=(cx - head_r_s, cy),
            p2=(cx + head_r_s, cy),
            base=(cx, cy - ext - 8),
            angle=0,
            text=f"⌀{features.head.diameter:.2f}",
        )

        # View label
        msp.add_text(
            "TOP VIEW",
            dxfattribs={**_ANN, "insert": (cx - 12, cy + ext + 6), "height": 4.0},
        )

    def _draw_drive_recess(
        self,
        msp: Any,
        cx: float,
        cy: float,
        drive: str,
        size_mm: float,
        scale: float,
        head_r_mm: float | None = None,
    ) -> None:
        """Sketch the drive feature in the top view.

        For Torx/cross drives, `size_mm` may be a spec number (e.g. T25, #2),
        not a true mm dimension. We clamp the drawn extent to ~60% of the
        head radius so the recess never escapes the head outline.
        """
        max_extent = (head_r_mm * 0.62) if head_r_mm else size_mm
        if drive == "hex_socket":
            # Hex socket — across-flats = drive_size in mm. Cap at 0.85·head_r.
            af = min(size_mm, (head_r_mm or size_mm) * 1.5)
            r = af / 2 / math.cos(math.radians(30)) * scale
            pts = [
                (cx + r * math.cos(math.radians(60 * i + 30)),
                 cy + r * math.sin(math.radians(60 * i + 30)))
                for i in range(6)
            ]
            msp.add_lwpolyline(pts, close=True, dxfattribs=_OL)
        elif drive == "torx":
            # Six-lobe star — outer extent clamped to head.
            r_out = max_extent * scale
            r_in = max_extent * 0.72 * scale
            pts = []
            for i in range(36):
                theta = math.radians(i * 10)
                lobe = math.cos(6 * theta) * 0.5 + 0.5
                r = r_in + (r_out - r_in) * lobe
                pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
            msp.add_lwpolyline(pts, close=True, dxfattribs=_OL)
        elif drive == "cross":
            half = max_extent * scale
            wid = max_extent * 0.27 * scale
            for ang in (0, math.pi / 2):
                ca, sa = math.cos(ang), math.sin(ang)
                rect = [
                    (cx + ca * half - sa * wid, cy + sa * half + ca * wid),
                    (cx + ca * half + sa * wid, cy + sa * half - ca * wid),
                    (cx - ca * half + sa * wid, cy - sa * half - ca * wid),
                    (cx - ca * half - sa * wid, cy - sa * half + ca * wid),
                ]
                msp.add_lwpolyline(rect, close=True, dxfattribs=_OL)
        elif drive == "slotted":
            half = max_extent * scale
            wid = max_extent * 0.26 * scale
            rect = [
                (cx + half, cy + wid), (cx + half, cy - wid),
                (cx - half, cy - wid), (cx - half, cy + wid),
            ]
            msp.add_lwpolyline(rect, close=True, dxfattribs=_OL)

    def _draw_drive_recess_detail(
        self,
        msp: Any,
        features: PartFeatures,
        cx: float,
        cy: float,
        zoom: float,
    ) -> None:
        """Zoomed-in drive recess detail box (DETAIL B), ~zoom× actual size.

        Engineers want a clear view of the drive feature for the punch tool —
        at typical 1:1 production scale a Torx star is just a few mm across.
        This adds a labeled detail box at zoom× actual size with its own
        across-flats / radius callouts.
        """
        drive = features.head.drive_type.value
        size = features.head.drive_size
        if drive == "none" or not size:
            return

        head_r = features.head.diameter / 2
        # Detail uses absolute mm scale (zoom × 1.0), independent of base layout.
        detail_scale = zoom

        # Reuse the same recess sketcher at the boosted scale.
        self._draw_drive_recess(
            msp, cx, cy, drive, size, detail_scale, head_r_mm=head_r,
        )

        # Detail box around it (square framing).
        max_extent = head_r * 0.62
        box_r = max_extent * detail_scale + 6
        box = [
            (cx - box_r, cy - box_r),
            (cx + box_r, cy - box_r),
            (cx + box_r, cy + box_r),
            (cx - box_r, cy + box_r),
        ]
        msp.add_lwpolyline(box, close=True, dxfattribs={"layer": "DIMENSION"})

        # Title above box.
        msp.add_text(
            f"DETAIL B  ({zoom:.0f}:1)",
            dxfattribs={**_ANN, "insert": (cx - box_r, cy + box_r + 3), "height": 3.5},
        )

        # Drive-specific callout below box.
        callout: str
        if drive == "torx":
            callout = f"Torx 6-lobe  ⌀{size:.2f}"
        elif drive == "hex_socket":
            callout = f"Hex socket  AF {size:.2f}"
        elif drive == "cross":
            callout = f"Phillips ⌀{size:.2f}"
        elif drive == "slotted":
            callout = f"Slot {size:.2f} wide"
        else:
            callout = f"{drive} {size:.2f}"
        msp.add_text(
            callout,
            dxfattribs={**_ANN, "insert": (cx - box_r, cy - box_r - 5), "height": 3.0},
        )

        # Leader from top view (centered at top_cx,top_cy is implicit in layout)
        # to detail box. We don't know exact top-view origin here, so just
        # draw a short index pointer from the box edge towards the page center.
        msp.add_line(
            (cx - box_r, cy),
            (cx - box_r - 12, cy + 6),
            dxfattribs={"layer": "DIMENSION"},
        )

    # ------------------------------------------------------------------
    # Production / performance text panels
    # ------------------------------------------------------------------

    def _add_production_notes(
        self,
        msp: Any,
        features: PartFeatures,
        process_plan: ProcessPlan,
        x: float,
        y_top: float,
    ) -> None:
        """Left-margin panel: production process + performance requirements."""
        # 生产工艺 / Production process
        lines: list[str] = ["生产工艺 / Process:"]
        if process_plan.blank_diameter:
            lines.append(f"  线径 ⌀{process_plan.blank_diameter:.2f}")
        if process_plan.blank_length:
            lines.append(f"  Blank L={process_plan.blank_length:.1f}")
        for i, st in enumerate(process_plan.stations, 1):
            op = st.operation.value.replace("_", " ")
            lines.append(f"  {i}. {op}")
        for pp in (process_plan.post_processes or []):
            pname = pp.value if hasattr(pp, "value") else str(pp)
            lines.append(f"  • {pname.replace('_', ' ')}")

        lines.append("")
        lines.append("性能要求 / Spec:")
        lines.append(f"  Material: {features.material_grade}")
        lines.append(f"  Grade: {features.strength_grade}")
        if features.surface_treatment:
            lines.append(f"  Surface: {features.surface_treatment}")
        if features.hardness_min_hv or features.hardness_max_hv:
            lo = f"{features.hardness_min_hv:.0f}" if features.hardness_min_hv else "?"
            hi = f"{features.hardness_max_hv:.0f}" if features.hardness_max_hv else "?"
            lines.append(f"  HV {lo}–{hi}")
        if features.standard:
            lines.append(f"  Std: {features.standard}")

        for i, ln in enumerate(lines):
            style = "GB_CJK" if any(ord(c) > 127 for c in ln) else "GB_NOTE"
            msp.add_text(
                ln,
                dxfattribs={
                    "layer": "TEXT",
                    "style": style,
                    "height": 2.8,
                    "insert": (x, y_top - i * 4.5),
                },
            )

    # ------------------------------------------------------------------
    # Process breakdown silhouettes
    # ------------------------------------------------------------------

    def _draw_workpiece_silhouette(
        self,
        msp: Any,
        shape: Any,
        cx: float,
        cy: float,
        op_name: str,
        idx: int,
    ) -> None:
        """Draw a scaled intermediate workpiece silhouette with hatch and label."""
        scale = _fit_scale(shape)
        od_s   = shape.max_diameter / 2 * scale
        len_s  = shape.overall_length * scale
        head_r = (shape.head_diameter or shape.max_diameter) / 2 * scale
        head_h = (shape.head_height or 0) * scale
        shank_r = (shape.shank_diameter or shape.max_diameter) / 2 * scale

        # Build profile polygon
        if head_r > shank_r * 1.05 and head_h > 0:
            pts: list[tuple[float, float]] = [
                (cx,          cy),
                (cx + shank_r, cy),
                (cx + shank_r, cy + len_s - head_h),
                (cx + head_r,  cy + len_s - head_h),
                (cx + head_r,  cy + len_s),
                (cx,           cy + len_s),
            ]
        else:
            pts = [
                (cx,         cy),
                (cx + od_s,  cy),
                (cx + od_s,  cy + len_s),
                (cx,         cy + len_s),
            ]

        # Hatch (diagonal lines represent material)
        self._add_hatch(msp, pts)

        # Right half outline
        msp.add_lwpolyline(pts, close=True, dxfattribs=_OL)

        # Left half outline (mirror)
        left_pts = [(2 * cx - x, y) for x, y in pts]
        msp.add_lwpolyline(left_pts, close=True, dxfattribs=_OL)

        # Center line
        msp.add_line((cx, cy - 4), (cx, cy + len_s + 4), dxfattribs=_CTR)

        # Station label above
        station_label = f"S{idx}" if idx > 0 else "Blank"
        msp.add_text(
            f"{station_label} {op_name}",
            dxfattribs={**_TXT, "insert": (cx - od_s, cy + len_s + 6), "height": 3.0},
        )

        # Dimension note below
        msp.add_text(
            f"⌀{shape.max_diameter:.1f}×{shape.overall_length:.1f}L",
            dxfattribs={**_TXT, "insert": (cx - od_s, cy - 9), "height": 2.8},
        )

    # ------------------------------------------------------------------
    # Primitive helpers
    # ------------------------------------------------------------------

    def _add_hatch(
        self,
        msp: Any,
        boundary_pts: list[tuple[float, float]],
        layer: str = "HATCH",
    ) -> None:
        """Add ANSI31 cross-section hatch inside the given closed polygon."""
        if len(boundary_pts) < 3:
            return
        try:
            hatch = msp.add_hatch(color=8, dxfattribs={"layer": layer})
            hatch.set_pattern_fill("ANSI31", scale=1.5, angle=45)
            hatch.paths.add_polyline_path(
                [(x, y) for x, y in boundary_pts],
                is_closed=True,
            )
        except Exception as exc:
            logger.debug("hatch_failed", error=str(exc))

    def _add_linear_dim(
        self,
        msp: Any,
        p1: tuple[float, float],
        p2: tuple[float, float],
        base: tuple[float, float],
        angle: float = 0,
        text: str = "<>",
        tol_upper: float | None = None,
        tol_lower: float | None = None,
    ) -> None:
        """
        Add a rendered linear dimension entity.

        angle=0 measures horizontal distance, angle=90 measures vertical.
        base is a point ON the dimension line.
        Always calls .render() so geometry appears in LibreCAD/AutoCAD.
        """
        override: dict = {}
        if tol_upper is not None:
            override = {"dimtol": 1, "dimtp": tol_upper, "dimtm": tol_lower or 0.0}
        try:
            dim = msp.add_linear_dim(
                base=base,
                p1=p1,
                p2=p2,
                angle=angle,
                text=text,
                dimstyle="GB",
                override=override or None,
            )
            dim.render()
        except Exception as exc:
            logger.debug("dim_failed", error=str(exc))

    def _add_material_notes(
        self,
        msp: Any,
        params: DieComponentParams,
        x: float,
        y: float,
    ) -> None:
        """Add material, hardness, coating notes as text block."""
        notes = [
            f"Material: {params.material}",
            f"Hardness: HRC {params.hardness_hrc_min:.0f}–{params.hardness_hrc_max:.0f}",
            f"Surface Ra: {params.surface_roughness_ra} μm",
        ]
        if params.surface_treatment:
            notes.append(f"Coating: {params.surface_treatment} {params.coating_thickness_um or 3:.0f}μm")
        if params.approach_angle_deg:
            notes.append(f"Approach: {params.approach_angle_deg:.0f}°")

        for i, note in enumerate(notes):
            msp.add_text(note, dxfattribs={**_ANN, "insert": (x, y + i * 7)})


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

# Standard mechanical-drawing scales (drawn:real). Snap fitted scales to one of
# these so the title block can show a clean "n:1" or "1:n".
_STD_SCALES: list[float] = [50.0, 20.0, 10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1]


def _pick_scale(part_w: float, part_h: float, area_w: float, area_h: float,
                fill: float = 0.65) -> tuple[float, str]:
    """
    Choose the largest standard scale at which the part still fits inside
    `fill` × the available area. Returns (scale, label).
    """
    if part_w <= 0 or part_h <= 0:
        return 1.0, "1:1"
    raw = min((area_w * fill) / part_w, (area_h * fill) / part_h)
    chosen = _STD_SCALES[-1]
    for s in _STD_SCALES:
        if s <= raw:
            chosen = s
            break
    if chosen >= 1.0:
        label = f"{int(chosen)}:1" if chosen == int(chosen) else f"{chosen:.1f}:1"
    else:
        inv = 1.0 / chosen
        label = f"1:{int(inv)}" if inv == int(inv) else f"1:{inv:.1f}"
    return chosen, label


def _view_layout(area: tuple[float, float, float, float],
                 side_extent: tuple[float, float],
                 has_end_view: bool = True,
                 fill: float = 0.7) -> dict:
    """
    Compute view origins and a shared scale for a side view + optional end view.

    `area` is (x0, y0, x1, y1) of the drawing region (inside the title block).
    `side_extent` is the part's (length, max_diameter) in real-world mm.
    Returns dict with: scale, scale_label, side_origin (cx, cy), end_origin.
    """
    x0, y0, x1, y1 = area
    aw = x1 - x0
    ah = y1 - y0

    # Reserve right ~30% of width for the end view; remainder for the side view.
    if has_end_view:
        side_w = aw * 0.62
        end_w = aw * 0.28
    else:
        side_w = aw * 0.85
        end_w = 0.0

    length, max_dia = side_extent
    # Side view is drawn vertically (length on Y axis), so width occupied is
    # `max_dia` and height is `length`.
    scale, label = _pick_scale(max_dia, length, side_w, ah, fill=fill)

    side_cx = x0 + 30 + (side_w - 30) * 0.45
    side_cy = y0 + 50 + (ah - 60) * 0.45  # raised above title block

    end_cx = x0 + side_w + end_w * 0.5
    end_cy = side_cy

    return {
        "scale": scale,
        "scale_label": label,
        "side_origin": (side_cx, side_cy),
        "end_origin": (end_cx, end_cy),
        "side_w": side_w,
        "end_w": end_w,
    }


def _fit_scale(shape: Any) -> float:
    """Compute scale factor to fit workpiece silhouette in ~35mm tall area."""
    if not shape.overall_length or not shape.max_diameter:
        return 1.0
    return min(35.0 / shape.overall_length, 15.0 / (shape.max_diameter / 2), 1.5)
