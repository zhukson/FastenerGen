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
BORDER_LEFT = 25.0
BORDER_RIGHT = 5.0
BORDER_TOP = 5.0
BORDER_BOTTOM = 5.0

# Title block size (mm)
TITLE_BLOCK_WIDTH = 180.0
TITLE_BLOCK_HEIGHT = 40.0
TITLE_BLOCK_ROW_HEIGHT = 8.0

# ---------------------------------------------------------------------------
# Layer definitions
# ---------------------------------------------------------------------------
STANDARD_LAYERS: dict[str, dict[str, Any]] = {
    "OUTLINE":    {"color": 7,  "linetype": "Continuous", "lineweight": 50},
    "CENTER":     {"color": 1,  "linetype": "CENTER",      "lineweight": 25},
    "DIMENSION":  {"color": 5,  "linetype": "Continuous",  "lineweight": 25},
    "HIDDEN":     {"color": 5,  "linetype": "DASHED",      "lineweight": 25},
    "HATCH":      {"color": 8,  "linetype": "Continuous",  "lineweight": 13},
    "TEXT":       {"color": 7,  "linetype": "Continuous",  "lineweight": 25},
    "TITLEBLOCK": {"color": 7,  "linetype": "Continuous",  "lineweight": 35},
    "SECTION":    {"color": 6,  "linetype": "Continuous",  "lineweight": 25},
    "ANNOTATION": {"color": 4,  "linetype": "Continuous",  "lineweight": 25},
}

DIE_STEEL_GRADES: list[str] = [
    "SKD11", "DC53", "ASP2030", "SKH51", "Cr12MoV", "W6Mo5Cr4V2", "YG15", "YG20",
]

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
                doc.linetypes.get(props["linetype"])
            layer.dxf.linetype = props["linetype"]
        except Exception:
            layer.dxf.linetype = "Continuous"


def setup_text_styles(doc: DXFDocument) -> None:
    """
    Register GB standard text styles.

    Uses a CJK-capable TTF so Chinese labels (图号, 图名, 材料, ...) and
    the ⌀ / μ glyphs render correctly in the matplotlib preview backend.
    NotoSansCJK ships in the Docker image; WQY Zenhei is the fallback.
    """
    cjk_font = "NotoSansCJK-Regular.ttc"
    # DejaVu covers engineering glyphs (⌀ U+2300, μ U+03BC, ± U+00B1) that
    # NotoSansCJK lacks. Use CJK only where labels actually contain Chinese.
    eng_font = "DejaVuSans.ttf"
    styles = {
        "GB_TITLE": {"height": 7.0, "font": cjk_font},
        "GB_NOTE":  {"height": 3.5, "font": eng_font},
        "GB_DIM":   {"height": 3.5, "font": eng_font},
        "GB_CJK":   {"height": 3.5, "font": cjk_font},
    }
    for name, props in styles.items():
        if name not in doc.styles:
            s = doc.styles.new(name, dxfattribs={"font": props["font"]})
        else:
            s = doc.styles.get(name)
            s.dxf.font = props["font"]
        s.dxf.height = props["height"]

    # Override the default STANDARD style so any un-styled TEXT still
    # renders through matplotlib instead of the ezdxf default (txt.shx).
    # DejaVu covers ⌀, μ, ± — the glyphs we actually emit outside the
    # title block.
    if "Standard" in doc.styles:
        std = doc.styles.get("Standard")
        std.dxf.font = eng_font


def setup_dimension_style(doc: DXFDocument, style_name: str = "GB") -> None:
    """
    Configure dimension style matching GB/T 4458 standards.

    Uses architectural tick marks (ARCHTICK), 3.5mm text,
    blue dimension lines (color 5) and decimal units.
    """
    if style_name not in doc.dimstyles:
        style = doc.dimstyles.new(style_name)
    else:
        style = doc.dimstyles.get(style_name)

    # Arrow style: ARCHTICK (architectural slash)
    try:
        style.set_arrows(blk="ARCHTICK", size=2.5)
    except Exception:
        style.dxf.dimasz = 2.5

    style.dxf.dimtxt = 3.5     # text height mm
    style.dxf.dimgap = 1.5     # gap between extension line and text
    style.dxf.dimexe = 2.0     # extension line extension beyond dim line
    style.dxf.dimexo = 1.0     # extension line offset from origin
    style.dxf.dimdli = 8.0     # dimension line increment (baseline dims)
    style.dxf.dimtol = 0       # tolerances off by default (set per-dim)
    style.dxf.dimlunit = 2     # decimal units
    style.dxf.dimrnd = 0.001   # round to 0.001mm
    style.dxf.dimtfac = 0.6    # tolerance text scale factor
    style.dxf.dimclrd = 5      # dim line color: blue
    style.dxf.dimclre = 5      # ext line color: blue
    style.dxf.dimclrt = 7      # text color: white/black


class DrawingFrame:
    """Draw a standard GB/T drawing frame for a given paper size."""

    def draw(self, msp: Any, paper_size: str = "A3") -> tuple[float, float, float, float]:
        """Draw outer border and inner frame. Returns (x0, y0, x1, y1) of drawing area."""
        width, height = DRAWING_SIZES.get(paper_size, DRAWING_SIZES["A3"])

        msp.add_lwpolyline(
            [(0, 0), (width, 0), (width, height), (0, height)],
            close=True,
            dxfattribs={"layer": "TITLEBLOCK", "lineweight": 35},
        )

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
    """Draw a standard GB/T title block in the bottom-right of the drawing frame."""

    def draw(
        self,
        msp: Any,
        frame: tuple[float, float, float, float],
        data: TitleBlock,
    ) -> None:
        x0, y0, x1, y1 = frame
        w = TITLE_BLOCK_WIDTH
        h = TITLE_BLOCK_HEIGHT

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

        r = TITLE_BLOCK_ROW_HEIGHT
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

            mid_x = tb_x0 + w * 0.45
            y_text = tb_y0 + i * r + r * 0.3
            msp.add_text(
                label,
                dxfattribs={
                    "layer": "TITLEBLOCK",
                    "style": "GB_CJK",
                    "height": 2.5,
                    "insert": (tb_x0 + 2, y_text),
                },
            )
            msp.add_text(
                value,
                dxfattribs={
                    "layer": "TITLEBLOCK",
                    "style": "GB_CJK",
                    "height": 3.5,
                    "insert": (mid_x + 2, y_text),
                },
            )

        mid_x = tb_x0 + w * 0.45
        msp.add_line(
            (mid_x, tb_y0), (mid_x, tb_y1),
            dxfattribs={"layer": "TITLEBLOCK", "lineweight": 13},
        )
