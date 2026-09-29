"""
backend/app/main.py
SatQuery AI — FastAPI application factory.

Phase 0: minimal health endpoints to verify DB/Redis connectivity.
Phase 1 will add full router registration, auth middleware, rate limiting.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.auth import OperatorAuthMiddleware
from app.core.errors import SatQueryError, generic_error_handler, satquery_error_handler
from app.core.settings import settings

# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
log = structlog.get_logger("satquery")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("SatQuery AI starting", env=settings.app_env, data_mode=settings.data_mode)
    yield
    log.info("SatQuery AI shutting down")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title="SatQuery AI",
        description="Semantic Retrieval and Multi-Temporal Change Analysis of Satellite Imagery — SIH 26227",
        version="0.1.0",
        docs_url="/api/docs" if settings.app_env == "development" else None,
        redoc_url="/api/redoc" if settings.app_env == "development" else None,
        openapi_url="/api/openapi.json" if settings.app_env == "development" else None,
        lifespan=lifespan,
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ---- Single-Operator Auth Middleware (ADR-012) ----
    app.add_middleware(OperatorAuthMiddleware)

    # ---- Request ID middleware ----
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ---- Exception handlers ----
    app.add_exception_handler(SatQueryError, satquery_error_handler)  # type: ignore
    app.add_exception_handler(Exception, generic_error_handler)

    # ---- Health routes (Phase 0) ----
    @app.get("/api/health/live", tags=["health"])
    async def health_live():
        """Liveness: process is running."""
        return {"status": "ok", "service": "satquery-api"}

    @app.get("/api/health/ready", tags=["health"])
    async def health_ready():
        """Readiness: core dependencies (DB, Redis) are reachable."""
        db_ok = await _check_db()
        redis_ok = await _check_redis()
        status = "ok" if (db_ok and redis_ok) else "degraded"
        return {
            "status": status,
            "dependencies": {
                "database": "ok" if db_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
            },
        }

    @app.get("/api/health", tags=["health"])
    async def health():
        """Full health: DB, Redis, device, features."""
        db_ok = await _check_db()
        redis_ok = await _check_redis()
        device_info = _get_device_info()
        status = "ok" if (db_ok and redis_ok) else "degraded"
        return {
            "status": status,
            "app_env": settings.app_env,
            "data_mode": settings.data_mode,
            "dependencies": {
                "database": "ok" if db_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
            },
            "compute": device_info,
            "features": {
                "groq": settings.groq_available,
                "copernicus": settings.copernicus_available,
            },
        }

    # ---- Routers ----
    from app.api.query import router as query_router
    from app.api.aoi import router as aoi_router
    from app.api.scenes import router as scenes_router
    from app.api.jobs import router as jobs_router
    from app.api.rasters import router as rasters_router
    from app.api.search import router as search_router
    from app.api.change import router as change_router
    from app.api.timeline import router as timeline_router
    from app.api.provenance import router as provenance_router
    from app.api.assistant import router as assistant_router
    from app.api.reports import router as reports_router
    app.include_router(query_router)
    app.include_router(aoi_router)
    app.include_router(scenes_router)
    app.include_router(jobs_router)
    app.include_router(rasters_router)
    app.include_router(search_router)
    app.include_router(change_router)
    app.include_router(timeline_router)
    app.include_router(provenance_router)
    app.include_router(assistant_router)
    app.include_router(reports_router)

    # ---- TEST DATA banner route ----
    if settings.data_mode == "test":
        @app.get("/api/_test/status", tags=["test"])
        async def test_status():
            return {
                "data_mode": "test",
                "warning": "TEST DATA — Not real satellite imagery. Do not use for operational decisions.",
            }

    return app


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------
async def _check_db() -> bool:
    try:
        import asyncio
        import sqlalchemy as sa
        from app.core.database import get_engine

        async def _ping():
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(sa.text("SELECT 1"))
            return True

        return await asyncio.wait_for(_ping(), timeout=1.5)
    except Exception:
        return False


async def _check_redis() -> bool:
    try:
        import asyncio
        import redis.asyncio as aioredis

        async def _ping():
            client = aioredis.from_url(settings.redis_url, socket_connect_timeout=0.8, socket_timeout=0.8)
            try:
                await client.ping()
                return True
            finally:
                await client.aclose()

        return await asyncio.wait_for(_ping(), timeout=1.0)
    except Exception:
        return False


def _get_device_info() -> dict:
    try:
        import torch

        cuda = torch.cuda.is_available()
        if cuda:
            return {
                "device": "cuda",
                "gpu_count": torch.cuda.device_count(),
                "gpu_name": torch.cuda.get_device_name(0),
            }
        return {"device": "cpu"}
    except ImportError:
        return {"device": "unknown", "note": "PyTorch not importable"}


# ---------------------------------------------------------------------------
# WSGI entry-point
# ---------------------------------------------------------------------------
app = create_app()
