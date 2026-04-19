"""Custom exception hierarchy for FastenerGPT."""

from fastapi import Request
from fastapi.responses import JSONResponse


class FastenerGPTError(Exception):
    """Base exception for all application errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class DrawingParseError(FastenerGPTError):
    """Failed to parse a product drawing."""

    status_code = 422
    error_code = "DRAWING_PARSE_ERROR"


class DrawingUnsupportedFormatError(FastenerGPTError):
    """Drawing file format is not supported."""

    status_code = 415
    error_code = "UNSUPPORTED_FORMAT"


class DesignGenerationError(FastenerGPTError):
    """Design generation pipeline failed."""

    status_code = 500
    error_code = "DESIGN_GENERATION_ERROR"


class DesignVerificationError(FastenerGPTError):
    """Design failed verification checks after max retries."""

    status_code = 422
    error_code = "VERIFICATION_FAILED"


class LLMError(FastenerGPTError):
    """LLM API call failed."""

    status_code = 502
    error_code = "LLM_ERROR"


class RAGError(FastenerGPTError):
    """RAG retrieval failed."""

    status_code = 500
    error_code = "RAG_ERROR"


class GeometryGenerationError(FastenerGPTError):
    """3D geometry generation failed."""

    status_code = 500
    error_code = "GEOMETRY_ERROR"


class StorageError(FastenerGPTError):
    """Object storage operation failed."""

    status_code = 500
    error_code = "STORAGE_ERROR"


class NotFoundError(FastenerGPTError):
    """Requested resource not found."""

    status_code = 404
    error_code = "NOT_FOUND"


class ValidationError(FastenerGPTError):
    """Input validation failed."""

    status_code = 422
    error_code = "VALIDATION_ERROR"


async def fastenergpt_exception_handler(
    request: Request, exc: FastenerGPTError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )
