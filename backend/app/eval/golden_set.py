"""
Golden test set management.

Loads and manages hand-verified test cases from datasets/golden/*.json.
Each golden case has known-correct process plans and die parameters for
regression testing the design pipeline.

Implemented in Session 5.
"""

from pathlib import Path

from app.data.schemas import EvalReport, ExpectedDecisions, PartFeatures


GOLDEN_DIR = Path(__file__).parent / "datasets" / "golden"


def load_golden_cases() -> list[dict[str, object]]:
    """Load all golden test cases from the datasets/golden directory."""
    raise NotImplementedError("Implemented in Session 5")


def run_golden_eval() -> EvalReport:
    """Run the full pipeline on all golden cases and produce an eval report."""
    raise NotImplementedError("Implemented in Session 5")
