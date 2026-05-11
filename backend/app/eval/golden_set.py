"""Golden case helpers for Gong reasoning evaluation."""

from __future__ import annotations

from app.data.schemas import CaseRecord
from app.knowledge.loader import load_library


def load_factory_cases() -> list[CaseRecord]:
    """Return real factory DWG cases that can be used for leave-one-out eval."""
    return load_library().cases


def load_standard_cases() -> list[CaseRecord]:
    """Return standard-part cases that can be used for smoke tests."""
    return load_library().standards
