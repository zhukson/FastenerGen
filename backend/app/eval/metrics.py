"""
Automated quality metrics for design evaluation.

Metrics computed per design:
- Station count accuracy (exact match vs. expected)
- Blank dimension error (% deviation from expected)
- Operation sequence accuracy (Levenshtein similarity)
- Die material match (correct steel grade selected)
- Verification pass rate
- LLM cost per design (USD)

Implemented in Session 5.
"""

from app.data.schemas import DesignResult, ExpectedDecisions, MetricResult


def compute_metrics(result: DesignResult, expected: ExpectedDecisions) -> list[MetricResult]:
    """Compute all quality metrics comparing pipeline output to expected decisions."""
    raise NotImplementedError("Implemented in Session 5")


def aggregate_metrics(results: list[list[MetricResult]]) -> list[MetricResult]:
    """Aggregate per-case metrics into dataset-level statistics (mean, p90, etc.)."""
    raise NotImplementedError("Implemented in Session 5")
