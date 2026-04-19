"""
Parametric 3D die (cavity) models using CADQuery.

Each template function takes DieComponentParams and returns a CADQuery Workplane
representing the die insert with cavity geometry. Templates cover common die types:
open die, closed die, trimming die, etc.

Note: cadquery may require conda install.

Implemented in Session 4.
"""

try:
    import cadquery as cq  # type: ignore[import-untyped]

    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False

from app.data.schemas import DieComponentParams


def cylindrical_die(params: DieComponentParams) -> object:
    """Cylindrical die insert — forward extrusion of shank."""
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery not installed.")
    raise NotImplementedError("Implemented in Session 4")


def heading_die(params: DieComponentParams) -> object:
    """Open-top heading die — upsetting to form head."""
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery not installed.")
    raise NotImplementedError("Implemented in Session 4")


def flat_head_die(params: DieComponentParams, head_angle_deg: float = 90.0) -> object:
    """Closed die for flat (countersunk) head — final forming station."""
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery not installed.")
    raise NotImplementedError("Implemented in Session 4")


def trimming_die(params: DieComponentParams) -> object:
    """Trimming die — trims excess material from head flange."""
    if not CADQUERY_AVAILABLE:
        raise ImportError("cadquery not installed.")
    raise NotImplementedError("Implemented in Session 4")
