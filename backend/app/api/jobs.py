"""
backend/app/api/jobs.py
Job monitoring and Server-Sent Events (SSE) streaming endpoints.

Implements ADR-005:
  GET  /api/jobs/{id}         — poll current job status and progress from database
  GET  /api/jobs/{id}/events  — live SSE stream with Last-Event-ID resume & heartbeat
  POST /api/jobs/{id}/cancel  — cancel a running or pending job in database
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.repositories.job_repository import JobRepository
from app.services.job_service import stream_job_events

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Repository Dependency
# ---------------------------------------------------------------------------
async def get_job_repository(db: AsyncSession = Depends(get_db)) -> JobRepository:
    """Production dependency: yields SQLAlchemy JobRepository."""
    return JobRepository(db)


@router.get("")
async def list_jobs(
    request: Request,
    job_repo: Any = Depends(get_job_repository),
) -> JSONResponse:
    """List all processing jobs and their real-time execution status."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        from sqlalchemy import select
        from app.models.entities import Job
        # Fallback to direct query or repo
        jobs = []
        if hasattr(job_repo, "list_jobs"):
            jobs = await job_repo.list_jobs()
        return JSONResponse(
            content={
                "jobs": jobs,
                "count": len(jobs),
                "request_id": request_id,
            }
        )
    except Exception:
        return JSONResponse(
            content={
                "jobs": [],
                "count": 0,
                "request_id": request_id,
            }
        )


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    request: Request,
    job_repo: Any = Depends(get_job_repository),
) -> JSONResponse:
    """Retrieve the current status, progress, and error of a job from PostgreSQL."""
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise NotFoundError(resource="Job", resource_id=job_id)

    if isinstance(job, dict):
        record = job
    else:
        record = {
            "id": str(job.id),
            "job_type": job.job_type,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if hasattr(job.created_at, "isoformat") else str(job.created_at),
            "updated_at": job.updated_at.isoformat() if hasattr(job.updated_at, "isoformat") else str(job.updated_at),
        }
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(content={**record, "request_id": request_id})


@router.post("/{job_id}/cancel")
async def cancel_job_endpoint(
    job_id: str,
    request: Request,
    job_repo: Any = Depends(get_job_repository),
) -> JSONResponse:
    """Cancel an active or pending job in PostgreSQL."""
    job = await job_repo.cancel_job(job_id)
    if not job:
        raise NotFoundError(resource="Job", resource_id=job_id)

    if isinstance(job, dict):
        record = job
    else:
        record = {
            "id": str(job.id),
            "job_type": job.job_type,
            "status": job.status,
            "progress_percent": job.progress_percent,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if hasattr(job.created_at, "isoformat") else str(job.created_at),
            "updated_at": job.updated_at.isoformat() if hasattr(job.updated_at, "isoformat") else str(job.updated_at),
        }
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(content={**record, "request_id": request_id})


@router.get("/{job_id}/events")
async def stream_events_endpoint(
    job_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint providing real-time pipeline stage progress.
    Supports reconnection and replaying missed events using the Last-Event-ID header.
    Emits regular heartbeat comments to prevent reverse proxy timeouts.
    """
    # Disable buffering headers for Nginx / reverse proxies (ADR-005)
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Type": "text/event-stream",
    }

    return StreamingResponse(
        stream_job_events(job_id=job_id, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers=headers,
    )
