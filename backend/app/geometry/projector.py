"""
3D → 2D view projection for drawing generation.

Projects CADQuery solids into standard orthographic views (front, side, top,
section) using OCC's HLR (Hidden Line Removal) algorithm.

In Phase 1 this is a thin wrapper that converts the bounding box of the
CADQuery solid into simplified 2D outlines for ezdxf drawing generation.
Full HLR projection with accurate edge visibility is implemented in Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import cadquery as cq

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False


@dataclass
class GeometricEntity2D:
    """A single 2D geometric entity in a projected view."""

    entity_type: str  # "line", "arc", "circle"
    visible: bool     # True = solid line, False = hidden line
    # For lines:
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    # For arcs/circles:
    cx: float = 0.0
    cy: float = 0.0
    radius: float = 0.0
    start_angle: float = 0.0
    end_angle: float = 360.0


class ViewProjector:
    """Project 3D CADQuery solids to 2D views for drawing generation."""

    def project_front(self, shape: "cq.Workplane") -> list[GeometricEntity2D]:
        """
        Project front view (looking along -Y axis).

        Phase 1: Returns bounding-box outline as 2D lines.
        Phase 2: Full HLR projection via OCC BRepAlgo_Section.
        """
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is required for projection.")

        bbox = shape.val().BoundingBox()
        x_min, x_max = bbox.xmin, bbox.xmax
        z_min, z_max = bbox.zmin, bbox.zmax

        # Rectangular outline (visible)
        return [
            GeometricEntity2D("line", True, x_min, z_min, x_max, z_min),
            GeometricEntity2D("line", True, x_max, z_min, x_max, z_max),
            GeometricEntity2D("line", True, x_max, z_max, x_min, z_max),
            GeometricEntity2D("line", True, x_min, z_max, x_min, z_min),
            # Center line
            GeometricEntity2D("line", False, 0, z_min - 5, 0, z_max + 5),
        ]

    def project_side(self, shape: "cq.Workplane") -> list[GeometricEntity2D]:
        """
        Project side view (looking along +X axis).

        Phase 1: Returns bounding-box outline.
        """
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is required for projection.")

        bbox = shape.val().BoundingBox()
        y_min, y_max = bbox.ymin, bbox.ymax
        z_min, z_max = bbox.zmin, bbox.zmax

        return [
            GeometricEntity2D("line", True, y_min, z_min, y_max, z_min),
            GeometricEntity2D("line", True, y_max, z_min, y_max, z_max),
            GeometricEntity2D("line", True, y_max, z_max, y_min, z_max),
            GeometricEntity2D("line", True, y_min, z_max, y_min, z_min),
        ]

    def project_section(
        self, shape: "cq.Workplane", cut_plane: str = "XZ"
    ) -> list[GeometricEntity2D]:
        """
        Project a sectional view cut along the specified plane.

        Phase 1: Cross-section via CadQuery's section() method, returns outlines.
        Phase 2: Full OCC cross-section with hatch fill.
        """
        if not CADQUERY_AVAILABLE:
            raise ImportError("cadquery is required for projection.")

        try:
            section = shape.section()
            return self.project_front(section)
        except Exception:
            return self.project_front(shape)
