"""Health check endpoint."""

import time

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    environment: str


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    from app.core.config import settings

    return HealthResponse(
        status="ok",
        version="0.1.0",
        uptime_seconds=round(time.time() - _start_time, 2),
        environment=settings.environment,
    )
