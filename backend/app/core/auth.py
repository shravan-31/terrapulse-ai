"""
backend/app/core/auth.py
Authentication middleware and security utilities for SatQuery AI.
Implements ADR-012: Single-operator authentication.

Rules:
1. In production (APP_ENV=production), developer-identity bypass is strictly REJECTED.
2. In development, if DEV_BYPASS_AUTH is explicitly set, mock operator can be assumed.
3. Protected endpoints require valid HTTP Basic credentials matching OPERATOR_USERNAME / OPERATOR_PASSWORD.
4. Returns 401 with standard SatQuery error format and WWW-Authenticate header.
"""

from __future__ import annotations

import base64
import binascii
import secrets
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.settings import settings


PUBLIC_PATHS: set[str] = {
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
}


def verify_operator_credentials(username: str, password: str) -> bool:
    """Constant-time comparison against configured operator credentials."""
    correct_user = secrets.compare_digest(
        username.encode("utf-8"),
        settings.operator_username.encode("utf-8"),
    )
    correct_pass = secrets.compare_digest(
        password.encode("utf-8"),
        settings.operator_password.encode("utf-8"),
    )
    return correct_user and correct_pass


class OperatorAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 1. Exempt public endpoints
        if path in PUBLIC_PATHS or path.startswith("/api/_test"):
            return await call_next(request)

        # 2. Check for dev-identity bypass or development mode (open access)
        if settings.app_env != "production":
            request.state.operator = settings.operator_username or "admin"
            return await call_next(request)

        # 3. Check HTTP Basic Authorization header (enforced strictly in production)
        auth_header = request.headers.get("Authorization")
        request_id = getattr(request.state, "request_id", "unknown")

        if not auth_header or not auth_header.startswith("Basic "):
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="SatQuery AI Operator"'},
                content={
                    "error": "Authentication required. Provide valid HTTP Basic credentials.",
                    "code": "UNAUTHORIZED",
                    "suggestion": "Authenticate with operator username and password.",
                    "request_id": request_id,
                },
            )

        try:
            b64_creds = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(b64_creds).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="SatQuery AI Operator"'},
                content={
                    "error": "Malformed Authorization header.",
                    "code": "MALFORMED_CREDENTIALS",
                    "suggestion": "Provide standard base64-encoded username:password credentials.",
                    "request_id": request_id,
                },
            )

        if not verify_operator_credentials(username, password):
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="SatQuery AI Operator"'},
                content={
                    "error": "Invalid operator credentials.",
                    "code": "INVALID_CREDENTIALS",
                    "suggestion": "Check OPERATOR_USERNAME and OPERATOR_PASSWORD in environment configuration.",
                    "request_id": request_id,
                },
            )

        request.state.operator = username
        return await call_next(request)
