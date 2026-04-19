"""
3D → 2D view projection for drawing generation.

Projects 3D solids into standard orthographic views (front, side, top, section)
for use in ezdxf-based 2D drawing generation. Wraps PythonOCC HLR (Hidden Line
Removal) algorithm.

Implemented in Session 4.
"""

from pathlib import Path


def project_views(
    solid: object,
    views: list[str] | None = None,
) -> dict[str, list[object]]:
    """
    Project a 3D solid into 2D views.

    Args:
        solid: CADQuery / PythonOCC solid.
        views: List of view names to generate, e.g. ['front', 'side', 'section_A'].
               Defaults to ['front', 'side'].

    Returns:
        Dict mapping view name to list of 2D edge entities (visible + hidden).
    """
    raise NotImplementedError("Implemented in Session 4")
