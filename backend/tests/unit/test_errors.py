"""
backend/tests/unit/test_errors.py
Unit tests verifying error formatting and security.

Validates:
1. SatQueryError and subclasses produce structured responses with error, code, suggestion, request_id.
2. Generic exceptions NEVER expose stack traces or internal exception strings to the client.
3. Appropriate HTTP status codes are mapped for domain errors.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    SatQueryError,
    NoImageryError,
    InvalidAOIError,
    ModelMissingError,
    generic_error_handler,
    satquery_error_handler,
)


@pytest.fixture
def error_app():
    app = FastAPI()
    app.add_exception_handler(SatQueryError, satquery_error_handler)  # type: ignore
    app.add_exception_handler(Exception, generic_error_handler)

    @app.get("/test/domain-error")
    async def trigger_domain_error():
        raise NoImageryError(
            message="No scenes found for given AOI and date interval.",
            suggestion="Try expanding the search window or cloud coverage threshold.",
        )

    @app.get("/test/model-error")
    async def trigger_model_error():
        raise ModelMissingError(
            message="Checkpoint file missing: ChangeFormer_LEVIR.pth",
            suggestion="Download model weights using scripts/download_models.py.",
        )

    @app.get("/test/unhandled-crash")
    async def trigger_unhandled():
        raise ValueError("Sensitive internal DB connection error /secret/key/path failed")

    return app


@pytest.mark.asyncio
async def test_domain_error_structure(error_app):
    async with AsyncClient(transport=ASGITransport(app=error_app), base_url="http://test") as client:
        resp = await client.get("/test/domain-error")
        assert resp.status_code == 404
        data = resp.json()
        assert data["code"] == "NO_IMAGERY"
        assert "No scenes found" in data["error"]
        assert "expanding the search window" in data["suggestion"]
        assert "request_id" in data


@pytest.mark.asyncio
async def test_model_missing_error_structure(error_app):
    async with AsyncClient(transport=ASGITransport(app=error_app), base_url="http://test") as client:
        resp = await client.get("/test/model-error")
        assert resp.status_code == 503
        data = resp.json()
        assert data["code"] == "MODEL_MISSING"
        assert "Checkpoint file missing" in data["error"]


@pytest.mark.asyncio
async def test_generic_error_never_exposes_traceback(error_app):
    async with AsyncClient(transport=ASGITransport(app=error_app, raise_app_exceptions=False), base_url="http://test") as client:
        resp = await client.get("/test/unhandled-crash")
        assert resp.status_code == 500
        data = resp.json()
        assert data["code"] == "INTERNAL_ERROR"
        # Verify sensitive internal traceback / path is NEVER leaked
        assert "Sensitive internal DB connection error" not in data["error"]
        assert data["error"] == "An unexpected server error occurred."
        assert "request_id" in data

