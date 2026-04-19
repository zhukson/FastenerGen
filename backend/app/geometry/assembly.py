"""
Assembly positioning for punch + die + workpiece.

Positions individual 3D components into a per-station assembly view
aligned on the forming axis. Used to generate assembly preview renders
and interference checks.

Implemented in Session 4.
"""

from app.data.schemas import DieParameters, ShapeDescription


def position_station_assembly(
    punch: object,
    die: object,
    workpiece: ShapeDescription,
    station_number: int,
) -> object:
    """Position punch, die, and workpiece into an assembly for a forming station."""
    raise NotImplementedError("Implemented in Session 4")


def check_interference(punch: object, die: object, clearance_mm: float) -> bool:
    """Return True if punch fits in die with the specified clearance (no interference)."""
    raise NotImplementedError("Implemented in Session 4")
