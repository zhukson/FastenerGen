"""
Drawing upload, parsing, and understanding endpoints.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import DrawingParseError, DrawingUnsupportedFormatError
from app.core.logging import get_logger
from app.data.schemas import ParsedDrawing, PartFeatures

router = APIRouter()
logger = get_logger(__name__)

# Allowed file extensions and their MIME types
ALLOWED_EXTENSIONS = {".pdf", ".dwg", ".dxf", ".jpg", ".jpeg", ".png"}
UPLOAD_DIR = Path("/tmp/fastenergpt/uploads")


class DrawingUploadResponse(BaseModel):
    drawing_id: str
    filename: str
    file_type: str
    upload_path: str


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/drawings/upload", response_model=DrawingUploadResponse, tags=["drawings"])
async def upload_drawing(file: UploadFile = File(...)) -> DrawingUploadResponse:
    """
    Upload a product drawing file (PDF, DWG, DXF, JPG, PNG).

    Stores the file and returns a drawing_id for subsequent operations.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise DrawingUnsupportedFormatError(
            f"File format '{suffix}' not supported",
            detail=f"Supported formats: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    drawing_id = str(uuid.uuid4())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{drawing_id}{suffix}"

    content = await file.read()
    dest.write_bytes(content)

    logger.info(
        "drawing_uploaded",
        drawing_id=drawing_id,
        filename=file.filename,
        bytes=len(content),
    )

    return DrawingUploadResponse(
        drawing_id=drawing_id,
        filename=file.filename,
        file_type=suffix.lstrip("."),
        upload_path=str(dest),
    )


# ---------------------------------------------------------------------------
# Parse (DXF structural extraction)
# ---------------------------------------------------------------------------

@router.post("/drawings/{drawing_id}/parse", response_model=ParsedDrawing, tags=["drawings"])
async def parse_drawing(drawing_id: str) -> ParsedDrawing:
    """
    Structurally parse an uploaded DXF/DWG drawing using ezdxf.

    Extracts dimensions, text, layer names, and title block data.
    For PDF/images, returns a minimal ParsedDrawing with just the file path.
    """
    path = _find_drawing(drawing_id)
    suffix = path.suffix.lower()

    if suffix in (".dxf", ".dwg"):
        from app.drawings.parser import DrawingParser

        try:
            parser = DrawingParser()
            parsed = parser.parse(path)
            return parsed
        except Exception as e:
            raise DrawingParseError(f"Failed to parse drawing: {e}", detail=str(e)) from e
    else:
        # PDF / image: return minimal metadata; actual extraction via Claude Vision
        from app.data.schemas import ConfidenceLevel

        return ParsedDrawing(
            file_path=str(path),
            file_format=suffix.lstrip("."),  # type: ignore[arg-type]
            parse_confidence=ConfidenceLevel.low,
        )


# ---------------------------------------------------------------------------
# Understand (Claude Vision extraction)
# ---------------------------------------------------------------------------

@router.post("/drawings/{drawing_id}/understand", response_model=PartFeatures, tags=["drawings"])
async def understand_drawing(drawing_id: str, hint: str = "") -> PartFeatures:
    """
    Extract structured PartFeatures from a drawing using Claude Opus 4.7 Vision.

    Runs 3× for self-consistency; returns majority-vote result.
    """
    if not settings.anthropic_api_key or settings.anthropic_api_key == "test-key":
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured. Set it in .env to use this endpoint.",
        )

    path = _find_drawing(drawing_id)

    from app.ai.drawing_reader import DrawingReader

    reader = DrawingReader()
    try:
        features = await reader.read_drawing(path, hint=hint)
        logger.info(
            "drawing_understood",
            drawing_id=drawing_id,
            part_number=features.part_number,
            overall_length=features.overall_length,
        )
        return features
    except Exception as e:
        raise DrawingParseError(f"Drawing understanding failed: {e}", detail=str(e)) from e


# ---------------------------------------------------------------------------
# Features (get stored extraction result)
# ---------------------------------------------------------------------------

@router.get("/drawings/{drawing_id}/features", tags=["drawings"])
async def get_drawing_features(drawing_id: str) -> dict:
    """
    Return previously extracted PartFeatures for a drawing.

    Full persistence (PostgreSQL storage) implemented in Session 3.
    For now returns the upload metadata only.
    """
    path = _find_drawing(drawing_id)
    return {
        "drawing_id": drawing_id,
        "file": path.name,
        "status": "uploaded",
        "note": "Call POST /drawings/{id}/understand to extract features",
    }


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

@router.get("/drawings/{drawing_id}/preview", tags=["drawings"])
async def get_drawing_preview(drawing_id: str) -> dict:
    """
    Return a preview image URL for an uploaded drawing.

    DXF → rendered to PNG via ezdxf matplotlib backend.
    PDF → first page as PNG.
    Images → returned as-is.
    """
    path = _find_drawing(drawing_id)
    # For now: return the file path; full preview generation in Session 3
    return {"drawing_id": drawing_id, "file_path": str(path), "format": path.suffix.lstrip(".")}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _find_drawing(drawing_id: str) -> Path:
    """Find an uploaded drawing by ID; raises 404 if not found."""
    for ext in ALLOWED_EXTENSIONS:
        path = UPLOAD_DIR / f"{drawing_id}{ext}"
        if path.exists():
            return path
    raise HTTPException(status_code=404, detail=f"Drawing '{drawing_id}' not found")
