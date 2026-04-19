"""
Synthetic data generation for testing and pre-seeding the RAG store.

Generates plausible product-die pairs based on engineering rules and
common fastener standards (M4-M16, various head types). Used to bootstrap
the system before real factory data is available.

Implemented in Session 5.
"""

from app.data.schemas import RAGCase


def generate_hex_bolt(
    nominal_diameter_mm: float,
    length_mm: float,
    material_grade: str = "10B21",
    strength_grade: str = "8.8",
) -> RAGCase:
    """Generate a synthetic hex bolt case with plausible die parameters."""
    raise NotImplementedError("Implemented in Session 5")


def generate_flat_head_screw(
    nominal_diameter_mm: float,
    length_mm: float,
    material_grade: str = "10B21",
    strength_grade: str = "8.8",
) -> RAGCase:
    """Generate a synthetic flat head (countersunk) screw case."""
    raise NotImplementedError("Implemented in Session 5")


def generate_synthetic_dataset(count: int = 100) -> list[RAGCase]:
    """Generate a mixed synthetic dataset for RAG pre-seeding."""
    raise NotImplementedError("Implemented in Session 5")
