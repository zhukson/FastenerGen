"""FastenerGPT backend — main FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import designs, drawings, eval, experiments, health
from app.core.config import settings
from app.core.exceptions import FastenerGPTError, fastenergpt_exception_handler
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info(
        "startup",
        environment=settings.environment,
        database_url=settings.database_url.split("@")[-1],  # hide credentials
    )

    # Pre-warm ezdxf's system font cache so DXF rendering finds
    # installed TTFs instead of falling back to txt.shx and logging
    # "no fonts available" on every render.
    try:
        from ezdxf.fonts import fonts as ezdxf_fonts
        ezdxf_fonts.build_system_font_cache()
        logger.info("ezdxf_font_cache_ready")
    except Exception as exc:
        logger.warning("ezdxf_font_cache_failed", error=str(exc))

    yield
    logger.info("shutdown")


app = FastAPI(
    title="FastenerGPT API",
    description="AI-powered die design for cold-heading fasteners",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(FastenerGPTError, fastenergpt_exception_handler)  # type: ignore[arg-type]

# Register routers
app.include_router(health.router, prefix="/api")
app.include_router(drawings.router, prefix="/api/v1")
app.include_router(designs.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")
app.include_router(experiments.router, prefix="/api/v1")
