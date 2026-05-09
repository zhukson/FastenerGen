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
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.data.schemas import (
    DesignResult,
    DesignStatus,
    PartFeatures,
    VerificationResult,
)

router = APIRouter()
logger = get_logger(__name__)

# In-memory store for MVP (Session 5+ migrates to PostgreSQL)
_designs: dict[str, DesignResult] = {}

# v2 (2026-05-01 pivot) — separate store for ProcessForming designs.
# Records:
#   {design_id: {"forming": ProcessForming, "part": PartFeatures,
#                "dxf": Path, "params": Path, "reasoning": Path,
#                "cited": list[str], "drawing_id": str}}
_v2_designs: dict[str, dict[str, Any]] = {}
V2_OUTPUT_ROOT = Path("/tmp/fastenergpt/v2_designs")


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

    # Match by: exact filename, relative subpath (e.g. "station_1/workpiece.stl"), or file_type
    norm_name = file_name.replace("\\", "/")
    for output_file in design.output_files:
        fp = Path(output_file.file_path)
        fp_norm = str(output_file.file_path).replace("\\", "/")
        if (fp.name == norm_name
                or fp_norm.endswith("/" + norm_name)
                or output_file.file_type == norm_name):
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


@router.get("/designs/{design_id}/dxf-preview/{file_name:path}", tags=["designs"])
async def dxf_preview(design_id: str, file_name: str) -> Any:
    """
    Render a DXF output file to PNG for in-browser preview.

    Uses ezdxf matplotlib backend. Dark background to match the UI.
    Returns image/png. Cached for 1 hour.
    """
    from fastapi.responses import Response

    design = _designs.get(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail=f"Design '{design_id}' not found")

    norm_name = file_name.replace("\\", "/")
    target_fp: Path | None = None
    for output_file in design.output_files:
        fp = Path(output_file.file_path)
        fp_norm = str(output_file.file_path).replace("\\", "/")
        if (
            (
                fp.name == norm_name
                or fp_norm.endswith("/" + norm_name)
                or output_file.file_type == norm_name
            )
            and fp.suffix.lower() == ".dxf"
            and fp.exists()
        ):
            target_fp = fp
            break

    if target_fp is None:
        raise HTTPException(status_code=404, detail=f"DXF '{file_name}' not found")

    try:
        import io

        import ezdxf
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: I001

        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        doc = ezdxf.readfile(str(target_fp))
        msp = doc.modelspace()

        fig = plt.figure(figsize=(14, 10), facecolor="#111827")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor("#111827")

        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    facecolor="#111827", edgecolor="none")
        plt.close(fig)
        buf.seek(0)

        return Response(
            content=buf.read(),
            media_type="image/png",
            headers={
                "Cache-Control": "max-age=3600",
                "Cross-Origin-Resource-Policy": "cross-origin",
            },
        )
    except Exception as exc:
        logger.error("dxf_preview_failed", error=str(exc), file=str(target_fp))
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}") from exc


@router.get("/rag/stats", tags=["designs"])
async def rag_stats() -> dict:
    """
    Return ChromaDB collection stats.

    Useful for verifying that RAG seeding completed successfully.
    Returns total case count broken down by nominal size and head type.
    """
    try:
        import chromadb

        from app.core.config import settings

        host_port = settings.chroma_url.replace("http://", "").replace("https://", "")
        host, _, port_str = host_port.partition(":")
        port = int(port_str) if port_str else 8000

        client = chromadb.HttpClient(host=host, port=port)
        collection = client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        count = collection.count()
        if count == 0:
            return {"total_cases": 0, "by_size": {}, "by_head_type": {}}

        # Fetch all metadata (limit to 2000 for safety)
        results = collection.get(limit=min(count, 2000), include=["metadatas"])
        metadatas = results.get("metadatas") or []

        by_size: dict[str, int] = {}
        by_head: dict[str, int] = {}
        for m in metadatas:
            size_key = f"M{m.get('nominal_dia', '?'):.0f}" if isinstance(m.get("nominal_dia"), float) else str(m.get("nominal_dia", "?"))
            head_key = str(m.get("head_type", "unknown"))
            by_size[size_key] = by_size.get(size_key, 0) + 1
            by_head[head_key] = by_head.get(head_key, 0) + 1

        return {
            "total_cases": count,
            "by_size": dict(sorted(by_size.items())),
            "by_head_type": dict(sorted(by_head.items())),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ChromaDB unavailable: {exc}") from exc


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
# v2 endpoints — single-output 过模图 pipeline (2026-05-01 pivot)
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
    dxf_url: str
    parameters_url: str
    reasoning_url: str
    preview_url: str
    gong_review_url: str
    verification: VerificationResult


@router.post("/designs/v2/generate", response_model=V2GenerateResponse, tags=["designs-v2"])
async def v2_generate(request: V2GenerateRequest) -> V2GenerateResponse:
    """v2 pipeline — input drawing -> single 过模图 DXF + reasoning."""
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
        "dxf": artifacts.dxf_path,
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
        dxf_url=f"{base}/dxf",
        parameters_url=f"{base}/parameters",
        reasoning_url=f"{base}/reasoning",
        preview_url=f"{base}/preview",
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


@router.get("/designs/v2/{design_id}/dxf", tags=["designs-v2"])
async def v2_dxf(design_id: str) -> FileResponse:
    rec = _v2_record(design_id)
    fp: Path = rec["dxf"]
    if not fp.exists():
        raise HTTPException(status_code=404, detail="DXF file missing on disk")
    return FileResponse(path=str(fp), filename=fp.name, media_type="application/octet-stream")


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


@router.get("/designs/v2/{design_id}/preview", tags=["designs-v2"])
async def v2_preview(design_id: str) -> Any:
    """Render the v2 DXF to PNG for in-browser preview."""
    from fastapi.responses import Response

    rec = _v2_record(design_id)
    target_fp: Path = rec["dxf"]
    if not target_fp.exists():
        raise HTTPException(status_code=404, detail="DXF missing on disk")

    try:
        import io

        import ezdxf
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        doc = ezdxf.readfile(str(target_fp))
        msp = doc.modelspace()

        fig = plt.figure(figsize=(14, 10), facecolor="#111827")
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_facecolor("#111827")
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp)

        buf = io.BytesIO()
        fig.savefig(
            buf, format="png", dpi=120, bbox_inches="tight",
            facecolor="#111827", edgecolor="none",
        )
        plt.close(fig)
        buf.seek(0)
        return Response(
            content=buf.read(),
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"},
        )
    except Exception as exc:
        logger.error("v2_preview_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}") from exc


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
