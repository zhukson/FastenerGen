"""
2D drawing generator using ezdxf.

Generates production drawings, die drawings, and process breakdown sheets
from structured die parameters. Applies GB standards for layers, dimensions,
and annotation styles.

Implemented in Session 4.
"""

from pathlib import Path

from app.data.schemas import DieParameters, PartFeatures, ProcessPlan


class DrawingGenerator:
    """Generate DXF drawings from structured die parameters."""

    def generate_production_drawing(
        self, features: PartFeatures, plan: ProcessPlan, output_path: Path
    ) -> Path:
        """Generate the product production drawing with process compensations."""
        raise NotImplementedError("Implemented in Session 4")

    def generate_punch_drawing(
        self, params: DieParameters, station: int, output_path: Path
    ) -> Path:
        """Generate punch drawing for a forming station."""
        raise NotImplementedError("Implemented in Session 4")

    def generate_die_drawing(
        self, params: DieParameters, station: int, output_path: Path
    ) -> Path:
        """Generate die (cavity) drawing for a forming station."""
        raise NotImplementedError("Implemented in Session 4")

    def generate_process_breakdown(
        self, plan: ProcessPlan, output_path: Path
    ) -> Path:
        """Generate process breakdown sheet showing intermediate shapes."""
        raise NotImplementedError("Implemented in Session 4")
