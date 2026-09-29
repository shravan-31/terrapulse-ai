"""
backend/app/core/database.py
SQLAlchemy async engine, connection pool, and session lifecycle management.

Implements:
- Async engine with pool pre-ping, connection timeouts, and connection recycling.
- Session factory and FastAPI dependency (get_db).
- Transaction context manager with automatic rollback on exception.
- Structured DatabaseUnavailableError when PostgreSQL/PostGIS is unreachable.
- Never silently falls back to in-memory storage in production mode.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.errors import DatabaseUnavailableError
from app.core.settings import settings

log = structlog.get_logger("satquery.database")

# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazily initialize and return the async engine."""
    global _engine, _sessionmaker
    if _engine is None:
        log.info(
            "Initializing SQLAlchemy async engine",
            url=settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        )
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=20,
            connect_args={"timeout": 5},
        )
        _sessionmaker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Retrieve the configured async session factory."""
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def reset_engine() -> None:
    """
    Dispose current engine connection pool and reset singletons.
    Critical on Windows with asyncio to avoid cross-event-loop connection reuse in tests.
    """
    global _engine, _sessionmaker
    if _engine is not None:
        try:
            await _engine.dispose()
        except Exception:
            pass
        _engine = None
        _sessionmaker = None


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an active AsyncSession per request.
    Wraps database operations in structured error handling so that
    connection failures return DatabaseUnavailableError instead of crashing.
    """
    sessionmaker_fn = get_sessionmaker()
    session = sessionmaker_fn()
    try:
        yield session
        await session.commit()
    except (OperationalError, ConnectionRefusedError, OSError) as exc:
        await session.rollback()
        log.error("Database connection failure in request session", error=str(exc))
        raise DatabaseUnavailableError(detail=str(exc)) from exc
    except DBAPIError as exc:
        await session.rollback()
        err_str = str(exc).lower()
        if any(k in err_str for k in ["does not exist", "connection refused", "failed to connect", "could not connect", "connection reset", "catalog", "authentication failed", "password", "timeout"]):
            log.error("Database unavailable in request session", error=str(exc))
            raise DatabaseUnavailableError(detail=str(exc)) from exc
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        log.error("Database error in request session", error=str(exc))
        raise
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Transaction Context Manager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def db_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for background tasks, Celery workers, and scripts
    requiring an isolated, transactional database session.
    """
    sessionmaker_fn = get_sessionmaker()
    session = sessionmaker_fn()
    try:
        yield session
        await session.commit()
    except (OperationalError, ConnectionRefusedError, OSError) as exc:
        await session.rollback()
        log.error("Database unavailable in transaction context", error=str(exc))
        raise DatabaseUnavailableError(detail=str(exc)) from exc
    except DBAPIError as exc:
        await session.rollback()
        err_str = str(exc).lower()
        if any(k in err_str for k in ["does not exist", "connection refused", "failed to connect", "could not connect", "connection reset", "catalog", "authentication failed", "password", "timeout"]):
            log.error("Database unavailable in transaction context", error=str(exc))
            raise DatabaseUnavailableError(detail=str(exc)) from exc
        raise
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Preflight Diagnostics
# ---------------------------------------------------------------------------
async def check_database_health() -> dict[str, Any]:
    """
    Ping the database and verify PostGIS version.
    Returns:
        {"connected": bool, "postgis": str | None, "error": str | None}
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            # Check basic connection
            await conn.execute(text("SELECT 1"))
            # Check PostGIS extension
            try:
                row = await conn.execute(text("SELECT PostGIS_Version()"))
                version = row.scalar()
                return {"connected": True, "postgis": str(version), "error": None}
            except Exception as postgis_err:
                return {
                    "connected": True,
                    "postgis": None,
                    "error": f"PostGIS extension missing: {postgis_err}",
                }
    except Exception as exc:
        return {"connected": False, "postgis": None, "error": str(exc)}
