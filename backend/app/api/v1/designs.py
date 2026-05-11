"""v2 ProcessForming design endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.data.schemas import (
    VerificationResult,
)

router = APIRouter()
logger = get_logger(__name__)

# v2 (2026-05-01 pivot) — separate store for ProcessForming designs.
# Records:
#   {design_id: {"forming": ProcessForming, "part": PartFeatures,
#                "params": Path, "reasoning": Path,
#                "cited": list[str], "drawing_id": str}}
_v2_designs: dict[str, dict[str, Any]] = {}
V2_OUTPUT_ROOT = Path("/tmp/fastenergpt/v2_designs")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class V2GenerateRequest(BaseModel):
    drawing_id: str
    prefer_category: str | None = None
    self_consistency_runs: int = Field(1, ge=1, le=3)
    exclude_case_ids: list[str] = []
    candidate_count: int = Field(1, ge=1, le=3)
    max_design_attempts: int = Field(1, ge=1, le=2)
    include_step3_images: bool = False
    design_model: Literal["sonnet", "opus"] = "sonnet"


class V2GenerateResponse(BaseModel):
    design_id: str
    drawing_id: str
    part_name_zh: str
    material: str
    station_count: int
    confidence: str
    cited_case_ids: list[str]
    parameters_url: str
    reasoning_url: str
    gong_review_url: str
    verification: VerificationResult


@router.post("/designs/v2/generate", response_model=V2GenerateResponse, tags=["designs-v2"])
async def v2_generate(request: V2GenerateRequest) -> V2GenerateResponse:
    """v2 pipeline — input drawing -> ProcessForming schema + reasoning."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

    drawing_path = _find_drawing(request.drawing_id)

    from app.ai.process_designer import ProcessDesigner

    design_id = uuid.uuid4().hex[:12]
    output_dir = V2_OUTPUT_ROOT / design_id
    model = (
        settings.primary_model
        if request.design_model == "opus"
        else settings.claude_model_die_design
    )
    designer = ProcessDesigner(model=model)
    try:
        artifacts = await designer.design(
            product_drawing_path=drawing_path,
            output_dir=output_dir,
            prefer_category=request.prefer_category,
            self_consistency_runs=request.self_consistency_runs,
            exclude_case_ids=request.exclude_case_ids,
            candidate_count=request.candidate_count,
            max_design_attempts=request.max_design_attempts,
            include_step3_images=request.include_step3_images,
        )
    except Exception as exc:
        logger.error("v2_design_failed", error=str(exc), drawing_id=request.drawing_id)
        raise HTTPException(status_code=500, detail=f"v2 generation failed: {exc}") from exc

    _v2_designs[design_id] = {
        "forming": artifacts.process_forming,
        "part": artifacts.part_features,
        "params": artifacts.parameters_path,
        "reasoning": artifacts.reasoning_path,
        "gong_review": artifacts.gong_review_path,
        "cited": artifacts.cited_case_ids,
        "drawing_id": request.drawing_id,
        "verification": artifacts.verification,
    }
    base = f"/api/v1/designs/v2/{design_id}"
    return V2GenerateResponse(
        design_id=design_id,
        drawing_id=request.drawing_id,
        part_name_zh=artifacts.process_forming.part_name_zh,
        material=artifacts.process_forming.material,
        station_count=artifacts.process_forming.station_count,
        confidence=artifacts.process_forming.confidence.value,
        cited_case_ids=artifacts.cited_case_ids,
        parameters_url=f"{base}/parameters",
        reasoning_url=f"{base}/reasoning",
        gong_review_url=f"{base}/gong-review",
        verification=artifacts.verification,
    )


@router.get("/designs/v2/{design_id}", tags=["designs-v2"])
async def v2_get(design_id: str) -> dict[str, Any]:
    record = _v2_designs.get(design_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"v2 design '{design_id}' not found")
    return {
        "design_id": design_id,
        "drawing_id": record["drawing_id"],
        "part_name_zh": record["forming"].part_name_zh,
        "material": record["forming"].material,
        "station_count": record["forming"].station_count,
        "confidence": record["forming"].confidence.value,
        "cited_case_ids": record["cited"],
        "process_forming": record["forming"].model_dump(mode="json"),
        "part_features": record["part"].model_dump(mode="json", exclude_none=True),
        "verification": record["verification"].model_dump(mode="json"),
    }


def _v2_record(design_id: str) -> dict[str, Any]:
    rec = _v2_designs.get(design_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"v2 design '{design_id}' not found")
    return rec


@router.get("/designs/v2/{design_id}/parameters", tags=["designs-v2"])
async def v2_parameters(design_id: str) -> FileResponse:
    rec = _v2_record(design_id)
    fp: Path = rec["params"]
    return FileResponse(path=str(fp), filename=fp.name, media_type="application/json")


@router.get("/designs/v2/{design_id}/reasoning", tags=["designs-v2"])
async def v2_reasoning(design_id: str) -> FileResponse:
    rec = _v2_record(design_id)
    fp: Path = rec["reasoning"]
    return FileResponse(path=str(fp), filename=fp.name, media_type="text/markdown")


@router.get("/designs/v2/{design_id}/gong-review", tags=["designs-v2"])
async def v2_gong_review(design_id: str) -> FileResponse:
    """Free-form Gong-style critique the LLM produced before committing JSON."""
    rec = _v2_record(design_id)
    fp: Path | None = rec.get("gong_review")
    if fp is None or not Path(fp).exists():
        raise HTTPException(status_code=404, detail="No gong_review available for this design")
    return FileResponse(path=str(fp), filename=Path(fp).name, media_type="text/markdown")


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
