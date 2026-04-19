"""Drawing upload and parsing endpoints. Implemented in Session 2."""

from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/drawings/upload", tags=["drawings"])
async def upload_drawing(file: UploadFile) -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 2")


@router.get("/drawings/{drawing_id}", tags=["drawings"])
async def get_drawing(drawing_id: str) -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 2")


@router.get("/drawings/{drawing_id}/preview", tags=["drawings"])
async def get_drawing_preview(drawing_id: str) -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 2")
