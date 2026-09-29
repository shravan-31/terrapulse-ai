"""
backend/tests/api/test_health.py
Phase 0 / Phase 1 gate: health endpoint tests.

Uses pytest-asyncio + httpx AsyncClient against the FastAPI app.
DB and Redis are mocked via monkeypatching for fast CI.
Real DB/Redis tests are in tests/integration/ and marked @pytest.mark.integration.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Liveness — always returns 200 even with no DB/Redis
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_live(client):
    resp = await client.get("/api/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "satquery-api"


# ---------------------------------------------------------------------------
# Readiness — degraded when DB/Redis unavailable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_ready_degraded_no_db(monkeypatch, client):
    """When DB is unavailable readiness should be degraded, not 500."""
    import app.main as main_mod

    async def fake_check_db():
        return False

    async def fake_check_redis():
        return False

    monkeypatch.setattr(main_mod, "_check_db", fake_check_db)
    monkeypatch.setattr(main_mod, "_check_redis", fake_check_redis)

    resp = await client.get("/api/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["database"] == "unavailable"
    assert body["dependencies"]["redis"] == "unavailable"


@pytest.mark.asyncio
async def test_health_ready_ok(monkeypatch, client):
    import app.main as main_mod

    async def fake_check_db():
        return True

    async def fake_check_redis():
        return True

    monkeypatch.setattr(main_mod, "_check_db", fake_check_db)
    monkeypatch.setattr(main_mod, "_check_redis", fake_check_redis)

    resp = await client.get("/api/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Full health — includes compute info
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_full(monkeypatch, client):
    import app.main as main_mod

    async def fake_check_db():
        return True

    async def fake_check_redis():
        return True

    monkeypatch.setattr(main_mod, "_check_db", fake_check_db)
    monkeypatch.setattr(main_mod, "_check_redis", fake_check_redis)

    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "compute" in body
    assert "features" in body
    assert "groq" in body["features"]
    assert "copernicus" in body["features"]


# ---------------------------------------------------------------------------
# Request ID propagation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_request_id_propagated(client):
    custom_id = "test-request-id-12345"
    resp = await client.get("/api/health/live", headers={"X-Request-ID": custom_id})
    assert resp.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_request_id_generated_if_missing(client):
    resp = await client.get("/api/health/live")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0


# ---------------------------------------------------------------------------
# Error handler: no stack traces exposed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_404_no_traceback(client):
    resp = await client.get("/api/nonexistent_route_xyz")
    assert resp.status_code == 404
    body = resp.json()
    # FastAPI 404s don't go through our handler but should still not leak tracebacks
    # Our custom errors will have the structured format
    assert "traceback" not in str(body).lower()


# ---------------------------------------------------------------------------
# TEST DATA mode
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_data_mode_test_banner(monkeypatch):
    import os
    monkeypatch.setenv("DATA_MODE", "test")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("OPERATOR_USERNAME", "test")
    monkeypatch.setenv("OPERATOR_PASSWORD", "testpassword")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")

    # Re-import settings with test env
    import importlib
    import app.core.settings as settings_mod
    importlib.reload(settings_mod)

    test_settings = settings_mod.Settings()
    assert test_settings.data_mode == "test"
