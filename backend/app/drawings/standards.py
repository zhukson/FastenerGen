"""
GB (Chinese National Standard) drawing standards for DXF output.

Implements GB/T 4458 (mechanical drawing) and GB/T 1182 (geometric tolerances).
Provides layers, paper sizes, title block template, and drawing frame.
"""

from __future__ import annotations

from typing import Any

import ezdxf
from ezdxf.document import Drawing as DXFDocument

from app.data.schemas import TitleBlock

# ---------------------------------------------------------------------------
# Paper sizes (mm, landscape orientation)
# ---------------------------------------------------------------------------
DRAWING_SIZES: dict[str, tuple[float, float]] = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

# Default border margins (mm)
BORDER_LEFT = 25.0    # wider left border for binding
BORDER_RIGHT = 5.0
BORDER_TOP = 5.0
BORDER_BOTTOM = 5.0

# Title block size (mm)
TITLE_BLOCK_WIDTH = 180.0
TITLE_BLOCK_HEIGHT = 40.0
TITLE_BLOCK_ROW_HEIGHT = 8.0

# ---------------------------------------------------------------------------
# Layer definitions: {name: {color, linetype, lineweight}}
# lineweight in mm × 100 (ezdxf convention)
# ---------------------------------------------------------------------------
STANDARD_LAYERS: dict[str, dict[str, Any]] = {
    "OUTLINE":    {"color": 7,  "linetype": "Continuous", "lineweight": 50},
    "CENTER":     {"color": 1,  "linetype": "CENTER",      "lineweight": 25},
    "DIMENSION":  {"color": 3,  "linetype": "Continuous",  "lineweight": 25},
    "HIDDEN":     {"color": 5,  "linetype": "DASHED",      "lineweight": 25},
    "HATCH":      {"color": 8,  "linetype": "Continuous",  "lineweight": 13},
    "TEXT":       {"color": 7,  "linetype": "Continuous",  "lineweight": 25},
    "TITLEBLOCK": {"color": 7,  "linetype": "Continuous",  "lineweight": 35},
    "SECTION":    {"color": 6,  "linetype": "Continuous",  "lineweight": 25},
    "ANNOTATION": {"color": 4,  "linetype": "Continuous",  "lineweight": 25},
}

# Die steel grades commonly used in cold heading tooling
DIE_STEEL_GRADES: list[str] = [
    "SKD11",       # D2 equivalent — general purpose
    "DC53",        # Improved D2 — better toughness
    "ASP2030",     # Powder metallurgy HSS — high wear resistance
    "SKH51",       # M2 HSS — high speed punches
    "Cr12MoV",     # Chinese D2 equivalent
    "W6Mo5Cr4V2",  # Chinese M2 equivalent
    "YG15",        # Cemented carbide — extreme wear resistance
    "YG20",        # Cemented carbide — tougher
]

# Surface treatment codes
SURFACE_TREATMENTS: dict[str, str] = {
    "TiN": "氮化钛",
    "TiCN": "碳氮化钛",
    "TiAlN": "铝氮化钛",
    "DLC": "类金刚石碳",
    "none": "不涂层",
}


def setup_layers(doc: DXFDocument) -> None:
    """Add all standard layers to a DXF document."""
    for name, props in STANDARD_LAYERS.items():
        if name not in doc.layers:
            layer = doc.layers.new(name)
        else:
            layer = doc.layers.get(name)
        layer.dxf.color = props["color"]
        layer.dxf.lineweight = props["lineweight"]
        try:
            if props["linetype"] != "Continuous":
                doc.linetypes.get(props["linetype"])  # ensure it exists
            layer.dxf.linetype = props["linetype"]
        except Exception:
            layer.dxf.linetype = "Continuous"


def setup_dimension_style(doc: DXFDocument, style_name: str = "GB") -> None:
    """
    Configure dimension style matching GB/T standards.

    - Text height: 3.5 mm
    - Arrow size: 3.5 mm (closed filled)
    - Extension line offset: 1.5 mm
    - Dimension line gap: 1.0 mm
    """
    if style_name not in doc.dimstyles:
        style = doc.dimstyles.new(style_name)
    else:
        style = doc.dimstyles.get(style_name)

    style.dxf.dimtxt = 3.5     # text height
    style.dxf.dimasz = 3.5     # arrow size
    style.dxf.dimexe = 2.0     # extension line extension
    style.dxf.dimexo = 1.5     # extension line offset from origin
    style.dxf.dimgap = 1.0     # gap between dim line and text
    style.dxf.dimclrd = 3      # dim line color (green = dimension layer)
    style.dxf.dimclre = 3      # extension line color
    style.dxf.dimclrt = 3      # text color


class DrawingFrame:
    """Draw a standard GB/T drawing frame for a given paper size."""

    def draw(self, msp: Any, paper_size: str = "A3") -> tuple[float, float, float, float]:
        """
        Draw the outer border and inner frame lines.

        Returns (x_min, y_min, x_max, y_max) of the drawing area (inside frame).
        """
        width, height = DRAWING_SIZES.get(paper_size, DRAWING_SIZES["A3"])

        # Outer border (paper edge)
        msp.add_lwpolyline(
            [(0, 0), (width, 0), (width, height), (0, height)],
            close=True,
            dxfattribs={"layer": "TITLEBLOCK", "lineweight": 35},
        )

        # Inner frame (accounting for margins)
        x0 = BORDER_LEFT
        y0 = BORDER_BOTTOM
        x1 = width - BORDER_RIGHT
        y1 = height - BORDER_TOP

        msp.add_lwpolyline(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
            close=True,
            dxfattribs={"layer": "TITLEBLOCK", "lineweight": 70},
        )

        return x0, y0, x1, y1


class TitleBlockTemplate:
    """
    Draw a standard GB/T title block in the bottom-right of the drawing frame.

    Supports Chinese text via ezdxf MTEXT entities with Unicode encoding.
    """

    def draw(
        self,
        msp: Any,
        frame: tuple[float, float, float, float],
        data: TitleBlock,
    ) -> None:
        """
        Draw the title block at the bottom-right of the drawing frame.

        Args:
            msp: modelspace
            frame: (x0, y0, x1, y1) from DrawingFrame.draw()
            data: title block content
        """
        x0, y0, x1, y1 = frame
        w = TITLE_BLOCK_WIDTH
        h = TITLE_BLOCK_HEIGHT

        # Title block outer rectangle (bottom-right)
        tb_x0 = x1 - w
        tb_y0 = y0
        tb_x1 = x1
        tb_y1 = y0 + h

        attribs = {"layer": "TITLEBLOCK", "lineweight": 35}

        # Outer rect
        msp.add_lwpolyline(
            [(tb_x0, tb_y0), (tb_x1, tb_y0), (tb_x1, tb_y1), (tb_x0, tb_y1)],
            close=True,
            dxfattribs=attribs,
        )

        r = TITLE_BLOCK_ROW_HEIGHT

        # Row dividers and content
        rows = [
            ("图号 / Part No.", data.part_number or ""),
            ("图名 / Title", data.title or ""),
            ("材料 / Material", data.material or ""),
            ("比例 / Scale", data.scale or "1:1"),
            ("版本 / Rev", data.revision or "A"),
        ]

        for i, (label, value) in enumerate(rows):
            y_line = tb_y0 + (i + 1) * r
            if y_line < tb_y1:
                msp.add_line(
                    (tb_x0, y_line), (tb_x1, y_line),
                    dxfattribs={"layer": "TITLEBLOCK", "lineweight": 13},
                )

            # Label (left half)
            mid_x = tb_x0 + w * 0.45
            y_text = tb_y0 + i * r + r * 0.3
            msp.add_text(
                label,
                dxfattribs={
                    "layer": "TITLEBLOCK",
                    "height": 2.5,
                    "insert": (tb_x0 + 2, y_text),
                },
            )
            # Value (right half)
            msp.add_text(
                value,
                dxfattribs={
                    "layer": "TITLEBLOCK",
                    "height": 3.5,
                    "insert": (mid_x + 2, y_text),
                    "style": "Standard",
                },
            )

        # Vertical divider between label and value
        mid_x = tb_x0 + w * 0.45
        msp.add_line(
            (mid_x, tb_y0), (mid_x, tb_y1),
            dxfattribs={"layer": "TITLEBLOCK", "lineweight": 13},
        )
