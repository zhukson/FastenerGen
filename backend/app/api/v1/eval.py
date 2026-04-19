"""Evaluation dashboard endpoints. Implemented in Session 5."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/eval/report", tags=["eval"])
async def get_eval_report() -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 5")


@router.post("/eval/run", tags=["eval"])
async def run_eval() -> dict[str, str]:
    raise NotImplementedError("Implemented in Session 5")


@router.get("/eval/cases", tags=["eval"])
async def list_eval_cases() -> list[dict[str, str]]:
    raise NotImplementedError("Implemented in Session 5")
