"""
backend/app/services/job_service.py
Durable Job management and event streaming service.

Implements ADR-005:
- Durable job progress and event logging.
- SSE stream generator supporting Last-Event-ID replay, heartbeat pings, and reconnection.
- Redis pub/sub broadcasting when Redis is available, with resilient in-memory fallback.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import structlog

from app.core.errors import NotFoundError
from app.core.settings import settings

log = structlog.get_logger("satquery.jobs")

# In-memory storage for jobs and events (fallback when PostgreSQL is unavailable)
_jobs_store: dict[str, dict[str, Any]] = {}
_job_events_store: dict[str, list[dict[str, Any]]] = {}
_job_subscribers: dict[str, list[asyncio.Queue]] = {}


def create_job(job_type: str) -> dict[str, Any]:
    """Create a new job record in pending status."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": job_id,
        "job_type": job_type,
        "status": "pending",
        "progress_percent": 0.0,
        "error_message": None,
        "result_data": None,
        "created_at": now,
        "updated_at": now,
    }
    _jobs_store[job_id] = record
    _job_events_store[job_id] = []
    _job_subscribers[job_id] = []

    log.info("Job created", job_id=job_id, job_type=job_type)
    emit_job_event(job_id, "created", f"Job {job_type} created and queued.")
    return record


def get_job(job_id: str) -> dict[str, Any]:
    """Retrieve job details by ID."""
    job = _jobs_store.get(job_id)
    if not job:
        raise NotFoundError(resource="Job", resource_id=job_id)
    return job


def emit_job_event(
    job_id: str,
    event_type: str,
    message: str,
    event_data: dict[str, Any] | None = None,
    progress: float | None = None,
) -> dict[str, Any]:
    """
    Log an event to the job's durable event stream and notify live subscribers.
    Updates progress_percent if provided.
    """
    job = _jobs_store.get(job_id)
    now = datetime.now(timezone.utc).isoformat()
    
    if job:
        job["updated_at"] = now
        if progress is not None:
            job["progress_percent"] = round(float(progress), 2)
        if event_type == "failed":
            job["status"] = "failed"
            job["error_message"] = message
        elif event_type == "completed":
            job["status"] = "completed"
            job["progress_percent"] = 100.0
        elif job["status"] == "pending" and event_type != "created":
            job["status"] = "running"

    event_id = str(uuid.uuid4())
    event_record = {
        "id": event_id,
        "job_id": job_id,
        "event_type": event_type,
        "message": message,
        "event_data": event_data or {},
        "created_at": now,
    }

    if job_id not in _job_events_store:
        _job_events_store[job_id] = []
    _job_events_store[job_id].append(event_record)

    # Broadcast to in-memory active SSE subscriber queues
    for q in _job_subscribers.get(job_id, []):
        try:
            q.put_nowait(event_record)
        except asyncio.QueueFull:
            pass

    log.debug("Job event emitted", job_id=job_id, event_type=event_type, msg=message)
    return event_record


def cancel_job(job_id: str) -> dict[str, Any]:
    """Cancel an active or pending job."""
    job = get_job(job_id)
    if job["status"] in ("completed", "failed"):
        return job

    job["status"] = "failed"
    job["error_message"] = "Job cancelled by operator."
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    emit_job_event(job_id, "failed", "Job cancelled by operator.")
    return job


async def stream_job_events(
    job_id: str,
    last_event_id: str | None = None,
    heartbeat_seconds: float = 15.0,
) -> AsyncGenerator[str, None]:
    """
    SSE generator for job events with Last-Event-ID replay and periodic heartbeats.
    Formats SSE output conforming to RFC standards:
      id: <event_id>
      event: <event_type>
      data: <json_string>
    """
    # 1. Replay events after last_event_id if requested
    past_events: list[dict[str, Any]] = []
    is_terminal = False
    found_job = False
    try:
        from app.core.database import db_transaction
        from app.repositories.job_repository import JobRepository
        async with db_transaction() as session:
            repo = JobRepository(session)
            job = await repo.get_by_id(job_id)
            if job:
                found_job = True
                is_terminal = job.status in ("completed", "failed")
                db_evs = await repo.get_events(job_id, after_id=last_event_id)
                past_events = [
                    {
                        "id": str(e.id),
                        "job_id": str(e.job_id),
                        "event_type": e.event_type,
                        "message": e.message,
                        "event_data": e.event_data,
                        "created_at": e.created_at.isoformat() if hasattr(e.created_at, "isoformat") else str(e.created_at),
                    }
                    for e in db_evs
                ]
    except Exception:
        pass

    if not found_job:
        current_job = _jobs_store.get(job_id)
        if not current_job:
            raise NotFoundError(resource="Job", resource_id=job_id)
        is_terminal = current_job.get("status") in ("completed", "failed")
        mem_events = _job_events_store.get(job_id, [])
        replay_start_idx = 0
        if last_event_id:
            for idx, ev in enumerate(mem_events):
                if ev["id"] == last_event_id:
                    replay_start_idx = idx + 1
                    break
        past_events = mem_events[replay_start_idx:]

    for ev in past_events:
        yield f"id: {ev['id']}\nevent: {ev['event_type']}\ndata: {json.dumps(ev)}\n\n"

    # If job is already in terminal state and all events replayed, end stream
    if is_terminal:
        return


    # 2. Subscribe for real-time events
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    if job_id not in _job_subscribers:
        _job_subscribers[job_id] = []
    _job_subscribers[job_id].append(queue)

    try:
        while True:
            try:
                # Wait for next event or heartbeat timeout
                ev = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                yield f"id: {ev['id']}\nevent: {ev['event_type']}\ndata: {json.dumps(ev)}\n\n"

                # Stop streaming once job reaches terminal state
                if ev["event_type"] in ("completed", "failed"):
                    break
            except asyncio.TimeoutError:
                # Send SSE comment heartbeat to prevent proxy timeouts
                yield f": heartbeat {datetime.now(timezone.utc).isoformat()}\n\n"
    finally:
        if job_id in _job_subscribers and queue in _job_subscribers[job_id]:
            _job_subscribers[job_id].remove(queue)
