"""
backend/app/core/errors.py
Custom error classes and FastAPI exception handlers for SatQuery AI.

All API errors return:
  { "error": str, "code": str, "suggestion": str, "request_id": str }

Never expose tracebacks to clients.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Error codes (keep in sync with frontend types)
# ---------------------------------------------------------------------------
class ErrorCode:
    NO_IMAGERY = "NO_IMAGERY"
    INVALID_AOI = "INVALID_AOI"
    MODEL_MISSING = "MODEL_MISSING"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    UPSTREAM_FAILURE = "UPSTREAM_FAILURE"
    EMPTY_INDEX = "EMPTY_INDEX"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    UNUSABLE_IMAGERY = "UNUSABLE_IMAGERY"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Base exception
# ---------------------------------------------------------------------------
class SatQueryError(Exception):
    """Base class for all SatQuery application errors."""

    def __init__(
        self,
        error: str = "",
        code: str = ErrorCode.INTERNAL_ERROR,
        suggestion: str = "",
        status_code: int = 500,
        extra: dict[str, Any] | None = None,
        message: str = "",
    ) -> None:
        err_text = error or message or "An error occurred."
        super().__init__(err_text)
        self.error = err_text
        self.code = code
        self.suggestion = suggestion
        self.status_code = status_code
        self.extra = extra or {}

    def to_dict(self, request_id: str) -> dict[str, Any]:
        return {
            "error": self.error,
            "code": self.code,
            "suggestion": self.suggestion,
            "request_id": request_id,
            **self.extra,
        }


# ---------------------------------------------------------------------------
# Specific error subclasses
# ---------------------------------------------------------------------------
class NoImageryError(SatQueryError):
    def __init__(
        self,
        message: str = "No usable imagery found for the requested AOI and date range.",
        suggestion: str = "Try a wider date range or lower cloud threshold.",
        error: str = "",
    ) -> None:
        super().__init__(
            error=error or message,
            code=ErrorCode.NO_IMAGERY,
            suggestion=suggestion,
            status_code=404,
        )


class InvalidAOIError(SatQueryError):
    def __init__(
        self,
        detail: str = "",
        suggestion: str = "Check coordinate order (lon, lat) and geometry validity.",
        message: str = "",
        error: str = "",
    ) -> None:
        err_text = error or message or f"Invalid area of interest: {detail}"
        super().__init__(
            error=err_text,
            code=ErrorCode.INVALID_AOI,
            suggestion=suggestion,
            status_code=422,
        )


class ModelMissingError(SatQueryError):
    def __init__(
        self,
        model_name: str = "",
        message: str = "",
        suggestion: str = "Run `python scripts/download_models.py` to download required weights.",
        error: str = "",
    ) -> None:
        err_msg = error or message or (f"Required model checkpoint not found: {model_name}" if model_name else "Required model checkpoint not found.")
        super().__init__(
            error=err_msg,
            code=ErrorCode.MODEL_MISSING,
            suggestion=suggestion,
            status_code=503,
        )


class LLMUnavailableError(SatQueryError):
    def __init__(self, detail: str = "") -> None:
        super().__init__(
            error=f"LLM service unavailable{': ' + detail if detail else ''}. Falling back to raw-text search.",
            code=ErrorCode.LLM_UNAVAILABLE,
            suggestion="The pipeline will continue without Groq. Set GROQ_API_KEY to enable LLM features.",
            status_code=503,
        )


class UpstreamFailureError(SatQueryError):
    def __init__(self, service: str, detail: str = "", retry_after: int | None = None) -> None:
        extra: dict[str, Any] = {}
        if retry_after is not None:
            extra["retry_after"] = retry_after
        super().__init__(
            error=f"Upstream service failure ({service}){': ' + detail if detail else ''}",
            code=ErrorCode.UPSTREAM_FAILURE,
            suggestion="The external service may be temporarily unavailable. Retry after a short delay.",
            status_code=502,
            extra=extra,
        )


class DatabaseUnavailableError(SatQueryError):
    def __init__(self, detail: str = "") -> None:
        super().__init__(
            error=f"Database service unavailable{': ' + detail if detail else ''}",
            code=ErrorCode.UPSTREAM_FAILURE,
            suggestion="Ensure PostgreSQL/PostGIS is running and reachable on configured port.",
            status_code=503,
        )



class EmptyIndexError(SatQueryError):
    def __init__(self) -> None:
        super().__init__(
            error="The vector index is empty. No imagery has been indexed yet.",
            code=ErrorCode.EMPTY_INDEX,
            suggestion="Ingest imagery first using POST /api/ingest before running semantic search.",
            status_code=404,
        )


class InsufficientObservationsError(SatQueryError):
    def __init__(self, detail: str = "") -> None:
        super().__init__(
            error=f"Insufficient usable observations for analysis{': ' + detail if detail else ''}.",
            code=ErrorCode.INSUFFICIENT_OBSERVATIONS,
            suggestion="Expand the date range, lower the cloud threshold, or ingest additional imagery.",
            status_code=422,
        )


class UnusableImageryError(SatQueryError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            error=f"Imagery is not usable: {reason}",
            code=ErrorCode.UNUSABLE_IMAGERY,
            suggestion="Select a different image pair or adjust quality thresholds.",
            status_code=422,
        )


class QuotaExceededError(SatQueryError):
    def __init__(self, resource: str = "Copernicus", retry_after: int | None = None) -> None:
        extra: dict[str, Any] = {}
        if retry_after is not None:
            extra["retry_after"] = retry_after
        super().__init__(
            error=f"Quota exceeded for {resource}.",
            code=ErrorCode.QUOTA_EXCEEDED,
            suggestion="Wait for quota reset or reduce the request scope.",
            status_code=429,
            extra=extra,
        )


class ResourceLimitError(SatQueryError):
    def __init__(self, resource: str, limit: str) -> None:
        super().__init__(
            error=f"Resource limit exceeded: {resource} (limit: {limit})",
            code=ErrorCode.RESOURCE_LIMIT,
            suggestion="Reduce the AOI size, date range, or number of scenes.",
            status_code=413,
        )


class NotFoundError(SatQueryError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            error=f"{resource} not found: {resource_id}",
            code=ErrorCode.NOT_FOUND,
            suggestion="Check the ID and try again.",
            status_code=404,
        )


class UnauthorizedError(SatQueryError):
    def __init__(self) -> None:
        super().__init__(
            error="Authentication required.",
            code=ErrorCode.UNAUTHORIZED,
            suggestion="Provide valid credentials.",
            status_code=401,
        )


class ValidationError(SatQueryError):
    def __init__(self, detail: str = "", message: str = "", error: str = "") -> None:
        err_msg = error or message or detail or "Invalid request parameters."
        super().__init__(
            error=err_msg,
            code=ErrorCode.VALIDATION_ERROR,
            suggestion="Check request fields and parameters.",
            status_code=422,
        )


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------
async def satquery_error_handler(request: Request, exc: SatQueryError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(request_id),
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler. Never exposes tracebacks.
    Logs the real exception internally (caller must configure logging).
    """
    import logging

    logging.getLogger("satquery").exception(
        "Unhandled exception",
        extra={"request_id": getattr(request.state, "request_id", "unknown")},
    )
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected server error occurred.",
            "code": ErrorCode.INTERNAL_ERROR,
            "suggestion": "Contact support with the request_id.",
            "request_id": request_id,
        },
    )
