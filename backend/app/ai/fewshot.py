"""
Few-shot XML formatter.

Converts RAGCase payload (Layer 2) into XML-formatted few-shot examples
(Layer 3) for LLM prompts. Never stored — always derived at query time.

Format is optimized for Claude's XML parsing; clearly delineates case
boundaries and highlights the most relevant features for the target part.

Implemented in Session 3.
"""

from app.data.schemas import PartFeatures, RetrievedCase


def payload_to_fewshot(cases: list[RetrievedCase], target: PartFeatures) -> str:
    """
    Convert retrieved cases to XML few-shot examples for LLM prompt injection.

    Args:
        cases: Top-N retrieved cases with similarity scores.
        target: The new part being designed (used to highlight relevant fields).

    Returns:
        XML string ready for injection into a prompt template.
    """
    raise NotImplementedError("Implemented in Session 3")
