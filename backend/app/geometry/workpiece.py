"""
Intermediate workpiece shape generation using CADQuery.

Generates 3D models of the workpiece (billet) at each forming station,
from blank wire stock through to near-finished part. Used for assembly
preview and volume conservation verification.

Implemented in Session 4.
"""

from app.data.schemas import ShapeDescription


def blank_wire(diameter_mm: float, length_mm: float) -> object:
    """Generate the initial wire stock (cylinder)."""
    raise NotImplementedError("Implemented in Session 4")


def intermediate_shape(shape: ShapeDescription) -> object:
    """Generate workpiece geometry for an intermediate forming station."""
    raise NotImplementedError("Implemented in Session 4")


def finished_part(shape: ShapeDescription) -> object:
    """Generate near-finished part shape after final forming station."""
    raise NotImplementedError("Implemented in Session 4")
