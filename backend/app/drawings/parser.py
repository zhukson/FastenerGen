"""
DWG/DXF drawing parser using ezdxf.

Reads existing product drawings and extracts entities, dimensions, and title
block information as structured data for the AI pipeline.

Implemented in Session 2.
"""

from pathlib import Path

from app.data.schemas import ParsedDrawing


class DrawingParser:
    """Parse DWG/DXF files into structured data using ezdxf."""

    def parse(self, file_path: Path) -> ParsedDrawing:
        """Parse a drawing file and return structured data."""
        raise NotImplementedError("Implemented in Session 2")

    def extract_dimensions(self, file_path: Path) -> list[dict[str, object]]:
        """Extract all dimension entities from a drawing."""
        raise NotImplementedError("Implemented in Session 2")

    def extract_title_block(self, file_path: Path) -> dict[str, str]:
        """Extract title block fields (part number, material, scale, etc.)."""
        raise NotImplementedError("Implemented in Session 2")
