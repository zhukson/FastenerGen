"""Design generation endpoints. Implemented in Session 3."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/designs", tags=["designs"])
async def create_design(drawing_id: str) -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 3")


@router.get("/designs", tags=["designs"])
async def list_designs() -> list[dict[str, str]]:
    raise NotImplementedError("Implemented in Session 3")


@router.get("/designs/{design_id}", tags=["designs"])
async def get_design(design_id: str) -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 3")


@router.post("/designs/{design_id}/feedback", tags=["designs"])
async def submit_feedback(design_id: str, action: str) -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 4")
