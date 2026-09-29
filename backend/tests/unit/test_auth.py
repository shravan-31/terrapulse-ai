"""
backend/tests/unit/test_auth.py
Unit tests for OperatorAuthMiddleware (ADR-012).

Tests:
1. Public health endpoints are accessible without credentials.
2. Protected routes require HTTP Basic credentials.
3. Invalid credentials return 401 with standard error format and WWW-Authenticate header.
4. Valid credentials succeed.
5. In production, dev bypass header is strictly rejected with 403.
"""

import base64
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.auth import OperatorAuthMiddleware
from app.core.settings import settings


@pytest.fixture
def auth_app():
    app = FastAPI()
    app.add_middleware(OperatorAuthMiddleware)

    @app.get("/api/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/api/protected")
    async def protected():
        return {"secret": "classified"}

    return app


@pytest.mark.asyncio
async def test_public_health_accessible_without_auth(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        resp = await client.get("/api/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_protected_route_requires_auth(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        resp = await client.get("/api/protected")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers
        data = resp.json()
        assert data["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_protected_route_rejects_invalid_creds(auth_app):
    invalid_b64 = base64.b64encode(b"wronguser:wrongpass").decode()
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        resp = await client.get(
            "/api/protected",
            headers={"Authorization": f"Basic {invalid_b64}"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_protected_route_accepts_valid_creds(auth_app):
    valid = f"{settings.operator_username}:{settings.operator_password}".encode()
    valid_b64 = base64.b64encode(valid).decode()
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        resp = await client.get(
            "/api/protected",
            headers={"Authorization": f"Basic {valid_b64}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"secret": "classified"}


@pytest.mark.asyncio
async def test_dev_bypass_rejected_in_production(auth_app, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as client:
        resp = await client.get(
            "/api/protected",
            headers={"X-Dev-Bypass": "true"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "DEV_BYPASS_FORBIDDEN"
