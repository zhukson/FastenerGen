"""
2D drawing generator using ezdxf.

Generates production-quality engineering drawings from structured parameters:
- Die component drawings (punch + die) with standard views and full dimensions
- Production drawings with process compensations
- Process breakdown sheets showing intermediate workpiece shapes

Output: DXF files following GB/T 4458 mechanical drawing standards.
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
)

logger = get_logger(__name__)


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
        """
        Generate a complete die component drawing (punch or die insert).

        Includes:
        - Main front view (profile with cross-section hatch)
        - Key dimensions with tolerances
        - Material, hardness, and surface treatment annotations
        - Standard frame and title block
        """
        output_path = Path(output_path)
        component = die_params.component_type  # "punch" or "die"

        doc = ezdxf.new(self._dxf_version)
        setup_layers(doc)
        setup_dimension_style(doc)
        msp = doc.modelspace()

        frame_coords = self._frame.draw(msp, paper_size)

        from app.data.schemas import TitleBlock
        title_data = TitleBlock(
            title=f"Station {station_number} — {component.title()} Drawing",
            material=die_params.material,
            scale="1:1",
        )
        self._title_block.draw(msp, frame_coords, title_data)

        x0, y0, x1, y1 = frame_coords
        # Draw view in the upper portion of the drawing area
        view_cx = x0 + (x1 - x0) * 0.35
        view_cy = y0 + (y1 - y0) * 0.55

        self._draw_die_component_view(msp, die_params, view_cx, view_cy)
        self._add_die_annotations(msp, die_params, station_number, x0, y0)

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
        setup_dimension_style(doc)
        msp = doc.modelspace()

        frame_coords = self._frame.draw(msp, paper_size)

        from app.data.schemas import TitleBlock
        title_data = TitleBlock(
            part_number=part_features.part_number,
            title=part_features.description,
            material=part_features.material_grade,
            scale="1:1",
            standard=part_features.standard,
        )
        self._title_block.draw(msp, frame_coords, title_data)

        x0, y0, x1, y1 = frame_coords
        view_cx = x0 + (x1 - x0) * 0.35
        view_cy = y0 + (y1 - y0) * 0.55

        self._draw_fastener_profile(msp, part_features, view_cx, view_cy)
        self._add_part_dimensions(msp, part_features, x0, y0)

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
        msp = doc.modelspace()

        frame_coords = self._frame.draw(msp, paper_size)
        x0, y0, x1, y1 = frame_coords

        from app.data.schemas import TitleBlock
        title_data = TitleBlock(title="Process Breakdown Sheet", scale="1:1")
        self._title_block.draw(msp, frame_coords, title_data)

        # Draw workpiece silhouettes spaced across the sheet
        n = process_plan.total_stations + 1  # include blank
        spacing = (x1 - x0) / (n + 1)
        shapes = [process_plan.stations[0].input_shape] + [
            s.output_shape for s in process_plan.stations
        ]

        for i, shape in enumerate(shapes):
            cx = x0 + spacing * (i + 1)
            cy = y0 + (y1 - y0) * 0.55
            self._draw_workpiece_silhouette(msp, shape, cx, cy)

            label = "Blank" if i == 0 else f"Station {i}"
            msp.add_text(
                label,
                dxfattribs={"layer": "TEXT", "height": 4.0, "insert": (cx - 10, cy - 35)},
            )

            # Arrow between shapes
            if i < len(shapes) - 1:
                msp.add_line(
                    (cx + shape.max_diameter / 2 + 2, cy),
                    (cx + spacing - shape.max_diameter / 2 - 2, cy),
                    dxfattribs={"layer": "DIMENSION"},
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(output_path))
        logger.info("process_breakdown_generated", path=str(output_path))
        return output_path

    # ------------------------------------------------------------------
    # Internal drawing helpers
    # ------------------------------------------------------------------

    def _draw_die_component_view(
        self,
        msp: Any,
        params: DieComponentParams,
        cx: float,
        cy: float,
    ) -> None:
        """Draw a simplified sectional front view of a die component."""
        od = params.outer_diameter / 2  # radius
        length = params.working_length
        id_r = (params.inner_diameter or 0) / 2

        attribs_outline = {"layer": "OUTLINE", "lineweight": 50}
        attribs_center = {"layer": "CENTER", "lineweight": 25}
        attribs_hidden = {"layer": "HIDDEN", "lineweight": 25}

        if params.component_type == "punch":
            # Punch: solid cylinder with shoulder
            shoulder_r = (params.shoulder_diameter or params.outer_diameter * 1.4) / 2
            shoulder_len = min(length * 0.3, 20.0)
            work_len = length

            # Outer profile (right side of symmetric view)
            pts = [
                (cx, cy + work_len + shoulder_len),
                (cx + shoulder_r, cy + work_len + shoulder_len),
                (cx + shoulder_r, cy + work_len),
                (cx + od, cy + work_len),
            ]
            # Approach / working face
            if params.geometry_type in (DieGeometryType.conical, DieGeometryType.flat_face):
                if params.approach_angle_deg and params.approach_angle_deg < 90:
                    # Tapered tip
                    taper_h = od / math.tan(math.radians(params.approach_angle_deg / 2))
                    pts += [(cx + od, cy + taper_h), (cx, cy)]
                else:
                    pts += [(cx + od, cy)]
            else:
                pts += [(cx + od, cy)]

            msp.add_lwpolyline(pts, dxfattribs=attribs_outline)
            # Mirror left side
            mirror_pts = [(2 * cx - x, y) for (x, y) in pts if x != cx]
            msp.add_lwpolyline(mirror_pts, dxfattribs=attribs_outline)

            # Center line
            msp.add_line(
                (cx, cy - 5), (cx, cy + work_len + shoulder_len + 5),
                dxfattribs=attribs_center,
            )

        else:
            # Die: hollow cylinder with bore
            msp.add_lwpolyline(
                [
                    (cx - od, cy),
                    (cx - od, cy + length),
                    (cx + od, cy + length),
                    (cx + od, cy),
                    (cx - od, cy),
                ],
                dxfattribs=attribs_outline,
            )
            # Bore (hidden lines)
            if id_r > 0:
                msp.add_line(
                    (cx - id_r, cy), (cx - id_r, cy + length),
                    dxfattribs=attribs_hidden,
                )
                msp.add_line(
                    (cx + id_r, cy), (cx + id_r, cy + length),
                    dxfattribs=attribs_hidden,
                )
                # Entry taper
                if params.approach_angle_deg:
                    entry_h = id_r / math.tan(math.radians(params.approach_angle_deg / 2 + 0.001))
                    entry_h = min(entry_h, length * 0.2)
                    entry_r_top = id_r * 1.5
                    msp.add_line(
                        (cx - entry_r_top, cy + length),
                        (cx - id_r, cy + length - entry_h),
                        dxfattribs=attribs_outline,
                    )
                    msp.add_line(
                        (cx + entry_r_top, cy + length),
                        (cx + id_r, cy + length - entry_h),
                        dxfattribs=attribs_outline,
                    )
            # Center line
            msp.add_line(
                (cx, cy - 5), (cx, cy + length + 5),
                dxfattribs=attribs_center,
            )

        # Hatch cross-section (simplified as diagonal lines)
        self._add_section_hatch(msp, cx, cy, od, min(length, 40))

    def _add_section_hatch(
        self, msp: Any, cx: float, cy: float, radius: float, height: float
    ) -> None:
        """Add simplified section hatching (diagonal lines)."""
        attribs = {"layer": "HATCH", "lineweight": 13}
        spacing = 4.0
        x = radius
        while x > spacing:
            msp.add_line(
                (cx + x - spacing, cy), (cx + x, cy + spacing),
                dxfattribs=attribs,
            )
            msp.add_line(
                (cx - x, cy), (cx - x + spacing, cy + spacing),
                dxfattribs=attribs,
            )
            x -= spacing

    def _add_die_annotations(
        self,
        msp: Any,
        params: DieComponentParams,
        station_number: int,
        x0: float,
        y0: float,
    ) -> None:
        """Add material, hardness, and surface treatment notes."""
        attribs = {"layer": "ANNOTATION", "height": 3.5}
        notes = [
            f"Material: {params.material}",
            f"Hardness: HRC {params.hardness_hrc_min:.0f}–{params.hardness_hrc_max:.0f}",
            f"Ra: {params.surface_roughness_ra} μm",
        ]
        if params.surface_treatment:
            coating = params.coating_thickness_um or 3.0
            notes.append(f"Coating: {params.surface_treatment} {coating:.0f}μm")
        if params.approach_angle_deg:
            notes.append(f"Approach angle: {params.approach_angle_deg:.0f}°")

        for i, note in enumerate(notes):
            msp.add_text(
                note,
                dxfattribs={**attribs, "insert": (x0 + 5, y0 + 80 + i * 8)},
            )

    def _draw_fastener_profile(
        self,
        msp: Any,
        features: PartFeatures,
        cx: float,
        cy: float,
    ) -> None:
        """Draw a simplified fastener profile (front view, top half)."""
        attribs = {"layer": "OUTLINE", "lineweight": 50}
        center = {"layer": "CENTER", "lineweight": 25}

        head_r = features.head.diameter / 2
        shank_r = features.shank.diameter / 2
        head_h = features.head.height
        shank_len = features.shank.length
        thread_len = features.thread.length

        total_len = head_h + shank_len + thread_len

        # Head
        msp.add_lwpolyline(
            [
                (cx - head_r, cy + total_len),
                (cx + head_r, cy + total_len),
                (cx + head_r, cy + total_len - head_h),
                (cx + shank_r, cy + total_len - head_h),
            ],
            dxfattribs=attribs,
        )
        msp.add_lwpolyline(
            [
                (cx - head_r, cy + total_len),
                (cx - head_r, cy + total_len - head_h),
                (cx - shank_r, cy + total_len - head_h),
            ],
            dxfattribs=attribs,
        )
        # Shank
        msp.add_line((cx + shank_r, cy + total_len - head_h), (cx + shank_r, cy + thread_len), dxfattribs=attribs)
        msp.add_line((cx - shank_r, cy + total_len - head_h), (cx - shank_r, cy + thread_len), dxfattribs=attribs)
        # Thread (dashed)
        msp.add_line((cx + shank_r, cy + thread_len), (cx + shank_r, cy), dxfattribs={"layer": "HIDDEN", "lineweight": 25})
        msp.add_line((cx - shank_r, cy + thread_len), (cx - shank_r, cy), dxfattribs={"layer": "HIDDEN", "lineweight": 25})
        # Bottom flat
        msp.add_line((cx - shank_r * 0.8, cy), (cx + shank_r * 0.8, cy), dxfattribs=attribs)
        # Center line
        msp.add_line((cx, cy - 5), (cx, cy + total_len + 5), dxfattribs=center)

    def _add_part_dimensions(
        self,
        msp: Any,
        features: PartFeatures,
        x0: float,
        y0: float,
    ) -> None:
        """Add key part dimension annotations as text notes."""
        attribs = {"layer": "DIMENSION", "height": 3.5}
        dims = [
            f"⌀{features.shank.diameter:.2f} (shank)",
            f"⌀{features.head.diameter:.2f} (head)",
            f"L={features.overall_length:.1f} mm (total)",
            f"Thread: {features.thread.spec}  L={features.thread.length:.1f}",
            f"Material: {features.material_grade}  Grade: {features.strength_grade}",
        ]
        if features.surface_treatment:
            dims.append(f"Surface: {features.surface_treatment}")
        for i, note in enumerate(dims):
            msp.add_text(note, dxfattribs={**attribs, "insert": (x0 + 5, y0 + 80 + i * 8)})

    def _draw_workpiece_silhouette(
        self,
        msp: Any,
        shape: Any,
        cx: float,
        cy: float,
    ) -> None:
        """Draw a simplified revolution silhouette of an intermediate workpiece."""
        attribs = {"layer": "OUTLINE", "lineweight": 50}
        od = shape.max_diameter / 2
        length = shape.overall_length
        scale = min(30.0 / length, 12.0 / od, 1.0)  # scale to fit

        od_s = od * scale
        len_s = length * scale

        # Simplified: rectangle (shank) with wider top (head)
        head_r = (shape.head_diameter or shape.max_diameter) / 2 * scale
        head_h = (shape.head_height or length * 0.15) * scale

        msp.add_lwpolyline(
            [
                (cx - head_r, cy + len_s),
                (cx + head_r, cy + len_s),
                (cx + head_r, cy + len_s - head_h),
                (cx + od_s, cy + len_s - head_h),
                (cx + od_s, cy),
                (cx - od_s, cy),
                (cx - od_s, cy + len_s - head_h),
                (cx - head_r, cy + len_s - head_h),
                (cx - head_r, cy + len_s),
            ],
            dxfattribs=attribs,
        )

        # Dimension note below
        msp.add_text(
            f"⌀{shape.max_diameter:.1f}×{shape.overall_length:.1f}",
            dxfattribs={"layer": "TEXT", "height": 2.5, "insert": (cx - 12, cy - 8)},
        )
