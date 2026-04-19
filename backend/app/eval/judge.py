"""
LLM-as-Judge evaluator.

Uses Claude Opus 4.7 to evaluate the quality of generated design reasoning
on dimensions that can't be measured numerically:
- Does the process sequence make engineering sense?
- Are the die material selections justified?
- Is the reasoning coherent and self-consistent?

Provides scores (1-5) with explanations for each dimension.

Implemented in Session 5.
"""

from app.data.schemas import DesignResult


async def judge_design(result: DesignResult) -> dict[str, object]:
    """
    Evaluate a generated design using Claude Opus 4.7 as judge.

    Returns dict with scores (1-5) and explanations for each evaluation dimension.
    """
    raise NotImplementedError("Implemented in Session 5")
