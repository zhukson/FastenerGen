"""
Drawing understanding evaluation.

Hand-annotated expected extraction results for the real 18149-D6 PDF drawing
(M6×33 flat head bolt, 10B21, 8.8 grade). Used to measure extraction accuracy
of the DrawingReader before and after prompt changes.

Run with: uv run pytest backend/tests/ai/test_drawing_reader.py -v
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.data.schemas import PartFeatures


@dataclass
class FieldExpectation:
    """Expected value for a single extracted field."""

    path: str           # dot-separated path e.g. "head.diameter"
    expected: Any       # exact value or (min, max) range tuple
    tolerance: float = 0.0   # acceptable absolute delta for numeric exact match
    required: bool = True    # if False, field may be null without failing


# ---------------------------------------------------------------------------
# Golden drawing test cases
# ---------------------------------------------------------------------------

GOLDEN_DRAWING_CASES: list[dict[str, Any]] = [
    {
        "id": "real_001_18149_D6",
        "file": "tests/test_data/18149-D6_M6X33_10B21.pdf",
        "hint": "M6×33 flat head bolt 10B21 8.8 grade",
        "expected": {
            "overall_length": (32.5, 33.5),
            "head_type": "flat",
            "head_diameter": (10.5, 13.0),
            "head_height": (2.5, 4.0),
            "shank_diameter": (5.5, 6.0),
            "thread_nominal_diameter": 6.0,
            "thread_pitch": 1.0,
            "thread_length": (19.0, 23.0),
            "material_grade": "10B21",
            "strength_grade": "8.8",
            "surface_treatment_contains": ["三价", "锌", "zinc"],  # any of these
            "hardness_hrc_min": (22.0, 28.0),
            "hardness_hrc_max": (28.0, 36.0),
        },
    }
]


class DrawingEvaluator:
    """Evaluate drawing extraction accuracy against golden expected values."""

    def evaluate(
        self,
        result: PartFeatures,
        expected: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compare extracted PartFeatures against expected values.

        Returns:
            {
                "score": float (0-1),
                "passed": int,
                "total": int,
                "details": [{field, expected, actual, passed}]
            }
        """
        details = []

        checks = [
            ("overall_length", result.overall_length, expected.get("overall_length")),
            ("head.type", result.head.type.value, expected.get("head_type")),
            ("head.diameter", result.head.diameter, expected.get("head_diameter")),
            ("head.height", result.head.height, expected.get("head_height")),
            ("shank.diameter", result.shank.diameter, expected.get("shank_diameter")),
            ("thread.nominal_diameter", result.thread.nominal_diameter, expected.get("thread_nominal_diameter")),
            ("thread.pitch", result.thread.pitch, expected.get("thread_pitch")),
            ("thread.length", result.thread.length, expected.get("thread_length")),
            ("material_grade", result.material_grade, expected.get("material_grade")),
            ("strength_grade", result.strength_grade, expected.get("strength_grade")),
        ]

        passed = 0
        for field_name, actual, exp in checks:
            if exp is None:
                continue
            ok = self._check_field(actual, exp)
            details.append({"field": field_name, "expected": exp, "actual": actual, "passed": ok})
            if ok:
                passed += 1

        # Surface treatment check (contains any keyword)
        st_keywords = expected.get("surface_treatment_contains")
        if st_keywords and result.surface_treatment:
            ok = any(kw.lower() in result.surface_treatment.lower() for kw in st_keywords)
            details.append({
                "field": "surface_treatment",
                "expected": f"contains any of {st_keywords}",
                "actual": result.surface_treatment,
                "passed": ok,
            })
            if ok:
                passed += 1

        # Hardness checks (stored as HRC in expected but HV in schema)
        # Convert: HRC ≈ HV * 0.1 (approximate; actual conversion is nonlinear)
        hrc_min_expected = expected.get("hardness_hrc_min")
        if hrc_min_expected and result.core_hardness_min_hrc is not None:
            ok = self._check_field(result.core_hardness_min_hrc, hrc_min_expected)
            details.append({
                "field": "core_hardness_min_hrc",
                "expected": hrc_min_expected,
                "actual": result.core_hardness_min_hrc,
                "passed": ok,
            })
            if ok:
                passed += 1

        total = len(details)
        score = passed / total if total > 0 else 0.0

        return {"score": score, "passed": passed, "total": total, "details": details}

    def _check_field(self, actual: Any, expected: Any) -> bool:
        """Check if actual matches expected (exact or range)."""
        if expected is None:
            return True
        if isinstance(expected, tuple) and len(expected) == 2:
            # Range check
            try:
                return expected[0] <= float(actual) <= expected[1]
            except (TypeError, ValueError):
                return False
        elif isinstance(expected, (int, float)):
            try:
                return abs(float(actual) - float(expected)) < 0.15
            except (TypeError, ValueError):
                return False
        elif isinstance(expected, str):
            return str(actual).lower() == expected.lower()
        return actual == expected
