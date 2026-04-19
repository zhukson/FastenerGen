"""
Quality scoring for generated designs.

Assigns a confidence score (high / medium / low) to each design based on
verification results, similarity to retrieved cases, and LLM self-reported
confidence. Flags low-confidence designs prominently in the UI.

Implemented in Session 3.
"""

from app.data.schemas import ConfidenceLevel, DesignResult, RetrievedCase, VerificationResult


def score_design(
    verification: VerificationResult,
    retrieved_cases: list[RetrievedCase],
    llm_confidence: str,
) -> ConfidenceLevel:
    """
    Compute overall design confidence from verification + retrieval + LLM signals.

    Rules:
    - Any failed ERROR-severity check → low
    - Top retrieved case similarity < 0.5 → low
    - All checks pass + top similarity ≥ 0.8 + LLM=high → high
    - Otherwise → medium
    """
    raise NotImplementedError("Implemented in Session 3")
