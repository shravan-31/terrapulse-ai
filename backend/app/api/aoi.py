"""
backend/app/api/aoi.py
AOI (Area of Interest) API endpoints.

Implements:
- POST /api/aoi       — validate and persist an AOI into PostgreSQL / PostGIS.
- GET  /api/aoi       — list all AOIs from the database.
- GET  /api/aoi/{id}  — retrieve a specific AOI by UUID.
- Uses SQLAlchemy/PostGIS repository by default.
- If database is unavailable, returns structured DatabaseUnavailableError (503).
  Never silently falls back to in-memory store in production.
- Supports injected in-memory repository fixture for isolated unit testing.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.entities import AOI
from app.repositories.aoi_repository import AOIRepository
from app.schemas.entities import AOICreate
from app.services.aoi_service import validate_aoi_geometry

router = APIRouter(prefix="/api/aoi", tags=["aoi"])


# ---------------------------------------------------------------------------
# In-memory test store (isolated test fixture only)
# ---------------------------------------------------------------------------
class InMemoryAOIRepository:
    """In-memory AOI store strictly used as an injected test fixture."""

    def __init__(self, store: dict[str, dict[str, Any]] | None = None) -> None:
        self._store = store if store is not None else {}

    async def create(
        self,
        name: str,
        geometry: dict[str, Any],
        area_km2: float,
        vertex_count: int,
        description: str | None = None,
        aoi_id: uuid.UUID | None = None,
    ) -> Any:
        aoi_uuid = aoi_id or uuid.uuid4()
        record = {
            "id": str(aoi_uuid),
            "name": name,
            "description": description,
            "geometry": geometry,
            "area_km2": area_km2,
            "vertex_count": vertex_count,
            "created_at": "2026-09-28T12:00:00Z",
            "updated_at": "2026-09-28T12:00:00Z",
        }
        self._store[str(aoi_uuid)] = record
        return record

    async def get_by_id(self, aoi_id: uuid.UUID | str) -> Any | None:
        return self._store.get(str(aoi_id))

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Any]:
        records = list(self._store.values())
        return records[offset : offset + limit]


_test_aoi_store: dict[str, dict[str, Any]] = {}
_test_repo = InMemoryAOIRepository(_test_aoi_store)
_aoi_store = _test_aoi_store


# ---------------------------------------------------------------------------
# Repository Dependency
# ---------------------------------------------------------------------------
async def get_aoi_repository(db: AsyncSession = Depends(get_db)) -> AOIRepository:
    """Production dependency: yields SQLAlchemy / PostGIS AOIRepository."""
    return AOIRepository(db)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("", status_code=201)
async def create_aoi(
    body: AOICreate,
    request: Request,
    repo: Any = Depends(get_aoi_repository),
) -> JSONResponse:
    """
    Validate and persist an Area of Interest.
    Persists to PostgreSQL/PostGIS. Returns structured error if DB is down.
    """
    validation = validate_aoi_geometry(body.geometry)

    aoi = await repo.create(
        name=body.name,
        description=body.description,
        geometry=body.geometry,
        area_km2=validation["area_km2"],
        vertex_count=validation["vertex_count"],
    )

    aoi_id_str = str(getattr(aoi, "id", aoi.get("id") if isinstance(aoi, dict) else aoi))
    response_data: dict[str, Any] = {
        "id": aoi_id_str,
        "name": body.name,
        "description": body.description,
        "geometry": body.geometry,
        "area_km2": validation["area_km2"],
        "vertex_count": validation["vertex_count"],
        "created_at": getattr(aoi, "created_at", "").isoformat() if hasattr(getattr(aoi, "created_at", None), "isoformat") else str(getattr(aoi, "created_at", "")),
        "updated_at": getattr(aoi, "updated_at", "").isoformat() if hasattr(getattr(aoi, "updated_at", None), "isoformat") else str(getattr(aoi, "updated_at", "")),
    }

    if validation["warnings"]:
        response_data["warnings"] = validation["warnings"]

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    response_data["request_id"] = request_id

    return JSONResponse(status_code=201, content=response_data)


@router.get("")
async def list_aois(
    request: Request,
    repo: Any = Depends(get_aoi_repository),
) -> JSONResponse:
    """List all persisted AOIs from database."""
    aois = await repo.list_all()
    results = []
    for a in aois:
        if isinstance(a, dict):
            results.append({**a, "id": str(a.get("id"))})
        else:
            results.append({
                "id": str(a.id),
                "name": a.name,
                "description": a.description,
                "geometry": a.geometry,
                "area_km2": a.area_km2,
                "vertex_count": a.vertex_count,
                "created_at": a.created_at.isoformat() if hasattr(a.created_at, "isoformat") else str(a.created_at),
                "updated_at": a.updated_at.isoformat() if hasattr(a.updated_at, "isoformat") else str(a.updated_at),
            })

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(content={"aois": results, "count": len(results), "request_id": request_id})


@router.get("/{aoi_id}")
async def get_aoi(
    aoi_id: str,
    request: Request,
    repo: Any = Depends(get_aoi_repository),
) -> JSONResponse:
    """Retrieve a specific AOI by UUID from database."""
    aoi = await repo.get_by_id(aoi_id)
    if not aoi:
        raise NotFoundError(resource="AOI", resource_id=aoi_id)

    if isinstance(aoi, dict):
        record = {**aoi, "id": str(aoi.get("id"))}
    else:
        record = {
            "id": str(aoi.id),
            "name": aoi.name,
            "description": aoi.description,
            "geometry": aoi.geometry,
            "area_km2": aoi.area_km2,
            "vertex_count": aoi.vertex_count,
            "created_at": aoi.created_at.isoformat() if hasattr(aoi.created_at, "isoformat") else str(aoi.created_at),
            "updated_at": aoi.updated_at.isoformat() if hasattr(aoi.updated_at, "isoformat") else str(aoi.updated_at),
        }

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(content={**record, "request_id": request_id})
