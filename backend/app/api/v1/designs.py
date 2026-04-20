"""
Design generation and retrieval endpoints.

POST /designs/generate  — run full pipeline for a part
GET  /designs           — list all designs
GET  /designs/{id}      — get design detail
GET  /designs/{id}/files/{file_name} — download output file
POST /designs/{id}/feedback — capture engineer feedback
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.data.schemas import ConfidenceLevel, DesignResult, DesignStatus, PartFeatures

router = APIRouter()
logger = get_logger(__name__)

# In-memory store for MVP (Session 5+ migrates to PostgreSQL)
_designs: dict[str, DesignResult] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DesignRequest(BaseModel):
    drawing_id: str | None = None
    features: PartFeatures | None = None
    hint: str = ""
    order_id: str | None = None


class DesignFeedback(BaseModel):
    action: str  # "accept" | "needs_changes" | "reject"
    notes: str = ""


class DesignSummary(BaseModel):
    design_id: str
    order_id: str
    description: str
    part_number: str | None
    thread_spec: str
    overall_length: float
    station_count: int
    confidence: str
    status: str
    cost_usd: float
    has_3d: bool
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/designs/generate", response_model=DesignResult, tags=["designs"])
async def generate_design(request: DesignRequest) -> DesignResult:
    """
    Run the full die design pipeline.

    Either provide `drawing_id` (Claude Vision will extract features) or
    provide `features` directly (for testing or re-runs).
    """
    part: PartFeatures | None = request.features

    # --- Step 1: Extract features if not provided ---
    if part is None:
        if not request.drawing_id:
            raise HTTPException(
                status_code=400,
                detail="Either drawing_id or features must be provided",
            )
        if not settings.anthropic_api_key:
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY not configured",
            )
        from app.ai.drawing_reader import DrawingReader

        drawing_path = _find_drawing(request.drawing_id)
        reader = DrawingReader()
        try:
            part = await reader.read_drawing(drawing_path, hint=request.hint)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Drawing extraction failed: {exc}") from exc

    assert part is not None

    # --- Step 2: RAG retrieval ---
    similar_cases: list[Any] = []
    retrieval_quality = "no_match"
    try:
        from app.ai.embeddings import EmbeddingService
        from app.ai.rag import FastenerRAG

        rag = FastenerRAG(embedding_service=EmbeddingService())
        similar_cases, retrieval_quality = await rag.retrieve_with_fallback(part, top_k=settings.rag_top_n)
        logger.info("rag_retrieved", count=len(similar_cases), quality=retrieval_quality)
    except Exception as exc:
        logger.warning("rag_retrieval_failed", error=str(exc))

    # --- Steps 3-6: DieDesigner ---
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

    from app.ai.designer import DieDesigner

    designer = DieDesigner()
    try:
        result = await designer.design(
            part=part,
            similar_cases=similar_cases,
            retrieval_quality=retrieval_quality,
            order_id=request.order_id,
        )
    except Exception as exc:
        logger.error("design_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Design generation failed: {exc}") from exc

    _designs[result.design_id] = result
    logger.info(
        "design_created",
        design_id=result.design_id,
        confidence=result.confidence,
        cost_usd=result.llm_cost_usd,
    )
    return result


@router.get("/designs", response_model=list[DesignSummary], tags=["designs"])
async def list_designs() -> list[DesignSummary]:
    """List all generated designs (most recent first)."""
    summaries: list[DesignSummary] = []
    for d in sorted(_designs.values(), key=lambda x: x.created_at, reverse=True):
        has_3d = any(f.format.value in ("stl", "step") for f in d.output_files)
        summaries.append(DesignSummary(
            design_id=d.design_id,
            order_id=d.order_id,
            description=d.part_features.description,
            part_number=d.part_features.part_number,
            thread_spec=d.part_features.thread.spec,
            overall_length=d.part_features.overall_length,
            station_count=d.process_plan.total_stations,
            confidence=d.confidence.value,
            status=d.status.value,
            cost_usd=d.llm_cost_usd,
            has_3d=has_3d,
            created_at=d.created_at.isoformat(),
        ))
    return summaries


@router.get("/designs/{design_id}", response_model=DesignResult, tags=["designs"])
async def get_design(design_id: str) -> DesignResult:
    """Get full design detail by ID."""
    design = _designs.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found")
    return design


@router.get("/designs/{design_id}/files/{file_name:path}", tags=["designs"])
async def download_file(design_id: str, file_name: str) -> FileResponse:
    """Download an output file (DXF, STL, STEP)."""
    design = _designs.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found")

    # Look up by file_name (last path component) or file_type
    for output_file in design.output_files:
        fp = Path(output_file.file_path)
        if fp.name == file_name or output_file.file_type == file_name:
            if not fp.exists():
                raise HTTPException(status_code=404, detail=f"File '{file_name}' not found on disk")
            media_type_map = {
                "dxf": "application/octet-stream",
                "stl": "model/stl",
                "step": "application/step",
                "json": "application/json",
            }
            media_type = media_type_map.get(fp.suffix.lstrip("."), "application/octet-stream")
            return FileResponse(path=str(fp), filename=fp.name, media_type=media_type)

    raise HTTPException(status_code=404, detail=f"File '{file_name}' not found in design '{design_id}'")


@router.post("/designs/{design_id}/feedback", tags=["designs"])
async def submit_feedback(design_id: str, feedback: DesignFeedback) -> dict[str, str]:
    """Capture engineer feedback for training data flywheel."""
    design = _designs.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found")

    valid_actions = {"accept", "needs_changes", "reject"}
    if feedback.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{feedback.action}'. Must be one of: {valid_actions}",
        )

    # Update status
    status_map = {
        "accept": DesignStatus.completed,
        "needs_changes": DesignStatus.flagged,
        "reject": DesignStatus.failed,
    }
    updated = design.model_copy(
        update={
            "status": status_map[feedback.action],
            "engineer_feedback": feedback.notes,
        }
    )
    _designs[design_id] = updated

    logger.info(
        "design_feedback",
        design_id=design_id,
        action=feedback.action,
        has_notes=bool(feedback.notes),
    )
    return {"design_id": design_id, "action": feedback.action, "status": "recorded"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_drawing(drawing_id: str) -> Path:
    from app.api.v1.drawings import ALLOWED_EXTENSIONS, UPLOAD_DIR

    for ext in ALLOWED_EXTENSIONS:
        path = UPLOAD_DIR / f"{drawing_id}{ext}"
        if path.exists():
            return path
    raise HTTPException(status_code=404, detail=f"Drawing '{drawing_id}' not found")
