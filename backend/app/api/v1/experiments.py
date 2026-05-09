"""Demo experiment endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.v1 import designs as designs_api
from app.core.config import settings
from app.core.logging import get_logger
from app.data.schemas import VerificationResult

router = APIRouter()
logger = get_logger(__name__)

EXPERIMENT_ROOT = Path(__file__).resolve().parents[3] / "experiments" / "m14_holdout"
M14_INPUT_PDF = EXPERIMENT_ROOT / "input" / "m14_product_input_page_001.pdf"
M14_INPUT_PREVIEW = EXPERIMENT_ROOT / "input" / "m14_product_input_page_001.png"
M14_GROUND_TRUTH_PDF = (
    EXPERIMENT_ROOT
    / "ground_truth"
    / "m14_forming_process_ground_truth_page_003_60-140L.pdf"
)
M14_GROUND_TRUTH_PREVIEW = (
    EXPERIMENT_ROOT
    / "ground_truth"
    / "m14_forming_process_ground_truth_page_003_60-140L.png"
)
M14_HOLDOUT_CASE_ID = "BD19046-P03-DIN912-M14-P2-0"
M14_PREFER_CATEGORY = "socket_cap_screw_DIN912"


class M14ExperimentRequest(BaseModel):
    quality_mode: bool = False
    self_consistency_runs: int = Field(1, ge=1, le=3)


class M14ExperimentResponse(BaseModel):
    experiment_id: str
    design_id: str
    drawing_id: str
    part_name_zh: str
    material: str
    station_count: int
    confidence: str
    cited_case_ids: list[str]
    experiment_folder: str
    dxf_url: str
    parameters_url: str
    reasoning_url: str
    preview_url: str
    gong_review_url: str
    input_pdf_url: str
    input_preview_url: str
    ground_truth_pdf_url: str
    ground_truth_preview_url: str
    ground_truth_dxf_url: str
    ground_truth_parameters_url: str
    verification: VerificationResult


def _pdf_page_count(path: Path) -> int | None:
    """Return PDF page count when pypdfium2 is available."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return None


@router.get("/experiments/m14", tags=["experiments"])
async def m14_info() -> dict[str, Any]:
    """Return static M14 leave-one-out experiment metadata."""
    return {
        "case_id": M14_HOLDOUT_CASE_ID,
        "prefer_category": M14_PREFER_CATEGORY,
        "input_pdf_exists": M14_INPUT_PDF.exists(),
        "input_pdf": str(M14_INPUT_PDF),
        "input_page_count": _pdf_page_count(M14_INPUT_PDF) if M14_INPUT_PDF.exists() else None,
        "input_source_page": 1,
        "ground_truth_pdf_exists": M14_GROUND_TRUTH_PDF.exists(),
        "ground_truth_source_page": 3,
        "ground_truth_note": (
            "Ground truth visual is the factory forming-process drawing for "
            "DIN912 M14 60-140L. It is linked for human comparison only and is "
            "not sent to the LLM runtime."
        ),
        "experiment_folder": str(EXPERIMENT_ROOT),
        "runtime_note": (
            "The M14 case is stored only under experiments/m14_holdout and is "
            "not loaded by app.knowledge.loader."
        ),
    }


@router.post(
    "/experiments/m14/run",
    response_model=M14ExperimentResponse,
    tags=["experiments"],
)
async def run_m14_experiment(request: M14ExperimentRequest) -> M14ExperimentResponse:
    """Run DIN912 M14 leave-one-out: input M14 PDF, exclude M14 ground truth."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    if not M14_INPUT_PDF.exists():
        raise HTTPException(status_code=404, detail=f"M14 input missing: {M14_INPUT_PDF}")
    page_count = _pdf_page_count(M14_INPUT_PDF)
    if page_count != 1:
        raise HTTPException(
            status_code=500,
            detail=(
                f"M14 holdout input must be exactly 1 product-drawing page; "
                f"found {page_count}. Refusing to run to avoid answer leakage."
            ),
        )

    from app.ai.process_designer import ProcessDesigner

    design_id = uuid.uuid4().hex[:12]
    output_dir = EXPERIMENT_ROOT / "runs" / design_id
    quality = request.quality_mode
    designer = ProcessDesigner(
        model=settings.primary_model if quality else settings.claude_model_die_design
    )
    try:
        artifacts = await designer.design(
            product_drawing_path=M14_INPUT_PDF,
            output_dir=output_dir,
            prefer_category=M14_PREFER_CATEGORY,
            self_consistency_runs=request.self_consistency_runs,
            exclude_case_ids=[M14_HOLDOUT_CASE_ID],
            candidate_count=3 if quality else 1,
            max_design_attempts=2 if quality else 1,
            include_step3_images=quality,
        )
    except Exception as exc:
        logger.error("m14_experiment_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"M14 experiment failed: {exc}") from exc

    designs_api._v2_designs[design_id] = {
        "forming": artifacts.process_forming,
        "part": artifacts.part_features,
        "dxf": artifacts.dxf_path,
        "params": artifacts.parameters_path,
        "reasoning": artifacts.reasoning_path,
        "gong_review": artifacts.gong_review_path,
        "cited": artifacts.cited_case_ids,
        "drawing_id": "experiment:m14_holdout",
        "verification": artifacts.verification,
    }

    base = f"/api/v1/designs/v2/{design_id}"
    return M14ExperimentResponse(
        experiment_id="m14_holdout",
        design_id=design_id,
        drawing_id="experiment:m14_holdout",
        part_name_zh=artifacts.process_forming.part_name_zh,
        material=artifacts.process_forming.material,
        station_count=artifacts.process_forming.station_count,
        confidence=artifacts.process_forming.confidence.value,
        cited_case_ids=artifacts.cited_case_ids,
        experiment_folder=str(EXPERIMENT_ROOT),
        dxf_url=f"{base}/dxf",
        parameters_url=f"{base}/parameters",
        reasoning_url=f"{base}/reasoning",
        preview_url=f"{base}/preview",
        gong_review_url=f"{base}/gong-review",
        input_pdf_url="/api/v1/experiments/m14/input-pdf",
        input_preview_url="/api/v1/experiments/m14/input-preview",
        ground_truth_pdf_url="/api/v1/experiments/m14/ground-truth/pdf",
        ground_truth_preview_url="/api/v1/experiments/m14/ground-truth/preview",
        ground_truth_dxf_url="/api/v1/experiments/m14/ground-truth/dxf",
        ground_truth_parameters_url="/api/v1/experiments/m14/ground-truth/parameters",
        verification=artifacts.verification,
    )


@router.get("/experiments/m14/input-pdf", tags=["experiments"])
async def m14_input_pdf() -> FileResponse:
    if not M14_INPUT_PDF.exists():
        raise HTTPException(status_code=404, detail="M14 input PDF missing")
    return FileResponse(
        path=str(M14_INPUT_PDF),
        filename=M14_INPUT_PDF.name,
        media_type="application/pdf",
    )


@router.get("/experiments/m14/input-preview", tags=["experiments"])
async def m14_input_preview() -> FileResponse:
    if not M14_INPUT_PREVIEW.exists():
        raise HTTPException(status_code=404, detail="M14 input preview missing")
    return FileResponse(
        path=str(M14_INPUT_PREVIEW),
        filename=M14_INPUT_PREVIEW.name,
        media_type="image/png",
    )


@router.get("/experiments/m14/ground-truth/pdf", tags=["experiments"])
async def m14_ground_truth_pdf() -> FileResponse:
    if not M14_GROUND_TRUTH_PDF.exists():
        raise HTTPException(status_code=404, detail="M14 ground-truth PDF missing")
    return FileResponse(
        path=str(M14_GROUND_TRUTH_PDF),
        filename=M14_GROUND_TRUTH_PDF.name,
        media_type="application/pdf",
    )


@router.get("/experiments/m14/ground-truth/preview", tags=["experiments"])
async def m14_ground_truth_preview() -> FileResponse:
    if not M14_GROUND_TRUTH_PREVIEW.exists():
        raise HTTPException(status_code=404, detail="M14 ground-truth preview missing")
    return FileResponse(
        path=str(M14_GROUND_TRUTH_PREVIEW),
        filename=M14_GROUND_TRUTH_PREVIEW.name,
        media_type="image/png",
    )


@router.get("/experiments/m14/ground-truth/dxf", tags=["experiments"])
async def m14_ground_truth_dxf() -> FileResponse:
    path = EXPERIMENT_ROOT / "ground_truth" / "process_forming_ground_truth.dxf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="M14 ground-truth DXF missing")
    return FileResponse(path=str(path), filename=path.name, media_type="application/octet-stream")


@router.get("/experiments/m14/ground-truth/parameters", tags=["experiments"])
async def m14_ground_truth_parameters() -> FileResponse:
    path = EXPERIMENT_ROOT / "ground_truth" / "process_parameters_ground_truth.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="M14 ground-truth parameters missing")
    return FileResponse(path=str(path), filename=path.name, media_type="application/json")
