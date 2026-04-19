"""
Core agentic design engine.

Orchestrates the full pipeline (Steps 1-6) as a single agentic workflow:
  Step 1: Drawing understanding (DrawingReader)
  Step 2: RAG retrieval (HybridRAG)
  Step 3: Process planning (LLM + few-shot)
  Step 4: Die parameter calculation (LLM + engineering rules)
  Step 5a: 3D model generation (CADQuery)
  Step 5b: 2D drawing generation (ezdxf)
  Step 6: Verification (rule-based; retries up to 2×)

Logs full LLM request/response traces and token costs for every call.

Implemented in Session 3.
"""

from pathlib import Path

from app.data.schemas import DesignResult, PartFeatures


class DesignEngine:
    """Orchestrates the full die design pipeline for a given product drawing."""

    async def run(self, drawing_path: Path, order_id: str) -> DesignResult:
        """
        Execute the full pipeline and return a complete DesignResult.

        On verification failure, automatically retries process planning
        with failure context injected into the prompt (max 2 retries).
        """
        raise NotImplementedError("Implemented in Session 3")

    async def plan_process(
        self, features: PartFeatures, fewshot_xml: str
    ) -> object:
        """Step 3: Generate ProcessPlan via LLM reasoning with few-shot examples."""
        raise NotImplementedError("Implemented in Session 3")

    async def calculate_die_parameters(
        self, features: PartFeatures, plan: object, fewshot_xml: str
    ) -> list[object]:
        """Step 4: Calculate DieParameters for each station."""
        raise NotImplementedError("Implemented in Session 3")
