"""
Regression testing framework.

Compares current pipeline results against a checked-in baseline (eval/baseline.json).
Fails CI if any metric regresses by more than the configured threshold.

Implemented in Session 5.
"""

from pathlib import Path

BASELINE_PATH = Path(__file__).parent.parent.parent.parent.parent / "eval" / "baseline.json"


def load_baseline() -> dict[str, object]:
    """Load the checked-in eval baseline."""
    raise NotImplementedError("Implemented in Session 5")


def check_regression(current: dict[str, object], baseline: dict[str, object]) -> list[str]:
    """
    Compare current metrics against baseline.

    Returns list of regression descriptions (empty if no regression).
    Thresholds: station_count_accuracy ≥ -5%, blank_dim_error ≤ +2%.
    """
    raise NotImplementedError("Implemented in Session 5")
