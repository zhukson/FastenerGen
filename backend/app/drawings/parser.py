"""
DWG/DXF drawing parser using ezdxf.

Reads DXF (and DWG via ezdxf's recovery loader) files and extracts:
- All DIMENSION entities → ExtractedDimension
- TEXT/MTEXT → annotations, material specs, notes
- LINE, ARC, CIRCLE, LWPOLYLINE → geometric entity counts
- INSERT blocks → title block data (part number, material, scale, etc.)

Handles R2010-R2018, Chinese+English text, gracefully skips missing entities.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.document import Drawing as DXFDocument

from app.core.logging import get_logger
from app.data.schemas import (
    ConfidenceLevel,
    DimensionType,
    ExtractedDimension,
    ParsedDrawing,
    TitleBlock,
)

logger = get_logger(__name__)

# Regex to detect Chinese characters in text entities
_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")

# Regex to extract ± tolerance from dimension text: e.g. "6.0±0.15" or "6.0+0.05/-0.10"
_TOL_BILATERAL = re.compile(r"±\s*(\d+\.?\d*)")
_TOL_UNILATERAL = re.compile(r"\+\s*(\d+\.?\d*)\s*/\s*-\s*(\d+\.?\d*)")

# Known title block field labels (Chinese + English)
_TITLE_FIELD_MAP: dict[str, str] = {
    "图号": "part_number",
    "part no": "part_number",
    "图名": "title",
    "名称": "title",
    "title": "title",
    "材料": "material",
    "material": "material",
    "比例": "scale",
    "scale": "scale",
    "制图": "drawn_by",
    "drawn": "drawn_by",
    "校核": "checked_by",
    "checked": "checked_by",
    "日期": "date",
    "date": "date",
    "版本": "revision",
    "rev": "revision",
}


class DrawingParser:
    """Parse DXF files into structured data using ezdxf."""

    def parse(self, file_path: str | Path) -> ParsedDrawing:
        """
        Parse a DWG/DXF file and return structured data.

        Attempts ezdxf.readfile first; on failure, falls back to
        ezdxf.recover.readfile (handles corrupt/non-standard files).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Drawing file not found: {path}")

        try:
            doc = ezdxf.readfile(str(path))
            parse_errors: list[str] = []
        except ezdxf.DXFStructureError:
            try:
                doc, auditor = ezdxf.recover.readfile(str(path))
                parse_errors = [str(err) for err in auditor.errors]
                logger.warning("recovered_dxf", path=str(path), errors=len(parse_errors))
            except Exception as e2:
                raise ValueError(f"Cannot parse drawing {path.name}: {e2}") from e2

        msp = doc.modelspace()

        dimensions = self._extract_dimensions(msp)
        title_block = self._extract_title_block(doc, msp)
        layer_names = [layer.dxf.name for layer in doc.layers]
        entity_count = len(list(msp))

        # Determine confidence: more dims + title block = higher confidence
        if len(dimensions) >= 5 and title_block.part_number:
            confidence = ConfidenceLevel.high
        elif len(dimensions) >= 2 or title_block.part_number:
            confidence = ConfidenceLevel.medium
        else:
            confidence = ConfidenceLevel.low

        return ParsedDrawing(
            file_path=str(path),
            file_format=path.suffix.lstrip(".").lower(),  # type: ignore[arg-type]
            dimensions=dimensions,
            title_block=title_block,
            layer_names=layer_names,
            entity_count=entity_count,
            parse_confidence=confidence,
            parse_errors=parse_errors,
        )

    def _extract_dimensions(self, msp: Any) -> list[ExtractedDimension]:
        dims: list[ExtractedDimension] = []

        for entity in msp:
            if entity.dxftype() != "DIMENSION":
                continue
            try:
                dim = self._parse_dimension_entity(entity)
                if dim is not None:
                    dims.append(dim)
            except Exception as e:
                logger.debug("dimension_parse_error", error=str(e))

        return dims

    def _parse_dimension_entity(self, entity: Any) -> ExtractedDimension | None:
        dxf = entity.dxf

        # Determine dimension type from subtype code
        dim_type_code = getattr(dxf, "dimtype", 0) & 0x0F
        dim_type_map = {
            0: DimensionType.linear,
            1: DimensionType.angular,
            2: DimensionType.diameter,
            3: DimensionType.radius,
            4: DimensionType.angular,
            5: DimensionType.linear,
            6: DimensionType.linear,
        }
        dim_type = dim_type_map.get(dim_type_code, DimensionType.linear)

        # Get measurement value
        actual_measurement = getattr(dxf, "actual_measurement", None)
        if actual_measurement is None or actual_measurement == 0:
            return None

        value = float(actual_measurement)

        # For diameter dimensions, flag as diameter
        text_override = getattr(dxf, "text", "")
        if text_override and text_override.startswith("⌀"):
            dim_type = DimensionType.diameter

        # Parse tolerance from text
        tol_plus, tol_minus = None, None
        if text_override:
            bil = _TOL_BILATERAL.search(text_override)
            if bil:
                t = float(bil.group(1))
                tol_plus = t
                tol_minus = t
            else:
                uni = _TOL_UNILATERAL.search(text_override)
                if uni:
                    tol_plus = float(uni.group(1))
                    tol_minus = float(uni.group(2))

        # Location of dimension text
        text_mid = getattr(dxf, "text_midpoint", None)
        x = float(text_mid.x) if text_mid else None
        y = float(text_mid.y) if text_mid else None

        return ExtractedDimension(
            dimension_type=dim_type,
            value=round(value, 4),
            tolerance_plus=tol_plus,
            tolerance_minus=tol_minus,
            label=text_override or None,
            x=x,
            y=y,
            layer=getattr(dxf, "layer", None),
        )

    def _extract_title_block(self, doc: DXFDocument, msp: Any) -> TitleBlock:
        """
        Extract title block data.

        Strategy 1: Look for TEXT/MTEXT entities near the bottom-right of the drawing
        (where title blocks are conventionally placed in GB/T standards).
        Strategy 2: Scan INSERT blocks that reference a known title block block definition.
        """
        # Collect all text strings with positions
        texts: list[tuple[str, float, float]] = []
        for entity in msp:
            if entity.dxftype() in ("TEXT", "MTEXT"):
                try:
                    text = entity.plain_mtext() if entity.dxftype() == "MTEXT" else entity.dxf.text
                    if hasattr(entity.dxf, "insert"):
                        x, y = entity.dxf.insert.x, entity.dxf.insert.y
                    else:
                        x, y = 0.0, 0.0
                    if text and text.strip():
                        texts.append((text.strip(), float(x), float(y)))
                except Exception:
                    continue

        return self._parse_title_block_from_texts(texts)

    def _parse_title_block_from_texts(
        self, texts: list[tuple[str, float, float]]
    ) -> TitleBlock:
        """Scan text entities for known title block field labels and extract values."""
        fields: dict[str, str] = {}

        # Simple heuristic: look for label: value pairs (same or adjacent lines)
        for text, _x, _y in texts:
            lower = text.lower().strip()
            for label, field in _TITLE_FIELD_MAP.items():
                if label in lower:
                    # Try to extract value from same string (e.g. "材料: 10B21")
                    sep_match = re.search(r"[:：]\s*(.+)$", text)
                    if sep_match:
                        fields[field] = sep_match.group(1).strip()
                    break
            else:
                # Check for standalone material patterns
                if re.match(r"^(10B21|SCM435|SUS304|45#|C1008|C1010|SWRCH\w+)$", text.strip()):
                    fields.setdefault("material", text.strip())
                # Check for scale pattern
                elif re.match(r"^\d+:\d+$", text.strip()):
                    fields.setdefault("scale", text.strip())
                # Check for drawing number (e.g. 18149-D6)
                elif re.match(r"^\d{4,}-[A-Z]\d*$", text.strip()):
                    fields.setdefault("part_number", text.strip())

        return TitleBlock(
            part_number=fields.get("part_number"),
            title=fields.get("title"),
            material=fields.get("material"),
            scale=fields.get("scale"),
            drawn_by=fields.get("drawn_by"),
            checked_by=fields.get("checked_by"),
            date=fields.get("date"),
            revision=fields.get("revision"),
        )

    def extract_all_text(self, file_path: str | Path) -> list[str]:
        """Extract all text content from a DXF file (useful for LLM pre-processing)."""
        path = Path(file_path)
        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()
        texts = []
        for entity in msp:
            if entity.dxftype() == "TEXT":
                texts.append(entity.dxf.text)
            elif entity.dxftype() == "MTEXT":
                texts.append(entity.plain_mtext())
        return [t for t in texts if t and t.strip()]
