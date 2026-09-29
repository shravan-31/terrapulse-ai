"""
backend/app/api/scenes.py
Satellite Scene discovery and ingestion API endpoints.

Implements:
  GET  /api/scenes         — list all persisted scenes from database
  GET  /api/scenes/{id}    — retrieve scene details by UUID or product_id
  POST /api/ingest         — start asynchronous scene ingestion job (HTTP 202)
                            persisting job into PostgreSQL and dispatching to Celery.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.repositories.job_repository import JobRepository
from app.repositories.scene_repository import SceneRepository
from app.schemas.entities import IngestRequest, IngestResponse
from app.services.ingest_service import run_ingestion_job

log = structlog.get_logger("satquery.api.scenes")

router = APIRouter(tags=["scenes"])


# ---------------------------------------------------------------------------
# Repository Dependencies (SQLAlchemy / PostGIS in normal mode)
# ---------------------------------------------------------------------------
async def get_scene_repository(db: AsyncSession = Depends(get_db)) -> SceneRepository:
    """Production dependency: yields SQLAlchemy / PostGIS SceneRepository."""
    return SceneRepository(db)


async def get_job_repository(db: AsyncSession = Depends(get_db)) -> JobRepository:
    """Production dependency: yields SQLAlchemy JobRepository."""
    return JobRepository(db)


@router.get("/api/scenes")
async def list_scenes(
    request: Request,
    scene_repo: Any = Depends(get_scene_repository),
) -> JSONResponse:
    """List all ingested satellite scenes from PostgreSQL."""
    scenes = await scene_repo.list_scenes()
    results = []
    for s in scenes:
        if isinstance(s, dict):
            results.append(s)
        else:
            results.append({
                "id": str(s.id),
                "product_id": s.product_id,
                "provider": s.provider,
                "acquisition_at": s.acquisition_at.isoformat() if hasattr(s.acquisition_at, "isoformat") else str(s.acquisition_at),
                "cloud_coverage_percent": s.cloud_coverage_percent,
                "footprint": s.footprint,
                "crs": s.crs,
                "metadata_json": s.metadata_json,
                "created_at": s.created_at.isoformat() if hasattr(s.created_at, "isoformat") else str(s.created_at),
            })
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        content={
            "scenes": results,
            "count": len(results),
            "request_id": request_id,
        }
    )


@router.get("/api/scenes/{scene_id}")
async def get_scene(
    scene_id: str,
    request: Request,
    scene_repo: Any = Depends(get_scene_repository),
) -> JSONResponse:
    """Retrieve details of a specific scene by UUID or product_id."""
    scene = await scene_repo.get_by_id(scene_id)
    if not scene:
        scene = await scene_repo.get_by_product_id(scene_id)
    if not scene:
        raise NotFoundError(resource="Scene", resource_id=scene_id)

    if isinstance(scene, dict):
        record = scene
    else:
        record = {
            "id": str(scene.id),
            "product_id": scene.product_id,
            "provider": scene.provider,
            "acquisition_at": scene.acquisition_at.isoformat() if hasattr(scene.acquisition_at, "isoformat") else str(scene.acquisition_at),
            "cloud_coverage_percent": scene.cloud_coverage_percent,
            "footprint": scene.footprint,
            "crs": scene.crs,
            "metadata_json": scene.metadata_json,
            "created_at": scene.created_at.isoformat() if hasattr(scene.created_at, "isoformat") else str(scene.created_at),
            "assets": [
                {
                    "id": str(a.id if hasattr(a, "id") else a.get("id")),
                    "asset_type": a.asset_type if hasattr(a, "asset_type") else a.get("asset_type"),
                    "local_path": a.local_path if hasattr(a, "local_path") else a.get("local_path"),
                    "checksum_sha256": a.checksum_sha256 if hasattr(a, "checksum_sha256") else a.get("checksum_sha256"),
                    "resolution_m": a.resolution_m if hasattr(a, "resolution_m") else a.get("resolution_m"),
                }
                for a in getattr(scene, "assets", scene.get("assets", []) if isinstance(scene, dict) else [])
            ],
        }
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(content={**record, "request_id": request_id})


@router.post("/api/ingest", status_code=202)
async def trigger_ingestion(
    body: IngestRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    job_repo: Any = Depends(get_job_repository),
) -> JSONResponse:
    """
    Trigger an asynchronous satellite imagery ingestion job for an AOI and date range.
    Persists durable job in PostgreSQL, dispatches to Celery (with resilient outbox fallback),
    and returns HTTP 202 with job_id.
    """
    job = await job_repo.create_job(job_type="ingest")
    job_id_str = str(getattr(job, "id", job.get("id") if isinstance(job, dict) else job))

    # Dispatch to Celery worker; if broker is unreachable, execute via background task runner
    dispatched_celery = False
    try:
        from app.workers.tasks import ingest_scene_task
        ingest_scene_task.delay(
            job_id=job_id_str,
            aoi_id=body.aoi_id,
            start_date_iso=body.start_date.isoformat(),
            end_date_iso=body.end_date.isoformat(),
            max_cloud_cover=body.max_cloud_cover,
            max_scenes=body.max_scenes,
        )
        dispatched_celery = True
        log.info("Dispatched ingestion task to Celery worker", job_id=job_id_str)
    except Exception as exc:
        log.warning(
            "Celery broker unavailable, falling back to asynchronous task runner",
            error=str(exc),
            job_id=job_id_str,
        )
        background_tasks.add_task(
            run_ingestion_job,
            job_id=job_id_str,
            aoi_id=body.aoi_id,
            start_date=body.start_date,
            end_date=body.end_date,
            max_cloud_cover=body.max_cloud_cover,
            max_scenes=body.max_scenes,
        )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id_str,
            "status": "pending",
            "celery_dispatched": dispatched_celery,
            "message": "Ingestion job queued successfully. Connect to SSE stream for live updates.",
            "request_id": request_id,
        },
    )
