"""
backend/app/repositories/job_repository.py
SQLAlchemy persistence repository for Jobs and JobEvents (ADR-005).

Provides durable state tracking and event history for asynchronous tasks.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import Job, JobEvent


class JobRepository:
    """Handles database persistence for asynchronous jobs and durable event streams."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(self, job_type: str, job_id: uuid.UUID | None = None) -> Job:
        """Create a new job in pending status."""
        job = Job(
            id=job_id or uuid.uuid4(),
            job_type=job_type,
            status="pending",
            progress_percent=0.0,
            error_message=None,
        )
        self.session.add(job)
        await self.session.flush()

        # Emit initial created event
        await self.emit_event(
            job_id=job.id,
            event_type="created",
            message=f"Job {job_type} created and queued.",
            event_data={"job_type": job_type},
        )
        return job

    async def get_by_id(self, job_id: uuid.UUID | str) -> Job | None:
        """Retrieve a job by its UUID with events preloaded."""
        if isinstance(job_id, str):
            try:
                job_uuid = uuid.UUID(job_id)
            except ValueError:
                return None
        else:
            job_uuid = job_id

        stmt = (
            select(Job)
            .options(selectinload(Job.events))
            .where(Job.id == job_uuid)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: uuid.UUID | str,
        status: str,
        progress_percent: float | None = None,
        error_message: str | None = None,
    ) -> Job | None:
        """Update job status and progress."""
        job = await self.get_by_id(job_id)
        if not job:
            return None

        job.status = status
        if progress_percent is not None:
            job.progress_percent = round(float(progress_percent), 2)
        if error_message is not None:
            job.error_message = error_message

        await self.session.flush()
        return job

    async def emit_event(
        self,
        job_id: uuid.UUID | str,
        event_type: str,
        message: str,
        event_data: dict[str, Any] | None = None,
        progress: float | None = None,
    ) -> JobEvent:
        """Persist a job event to the durable job_events table and update job status."""
        job = await self.get_by_id(job_id)
        if job:
            if progress is not None:
                job.progress_percent = round(float(progress), 2)
            if event_type == "failed":
                job.status = "failed"
                job.error_message = message
            elif event_type == "completed":
                job.status = "completed"
                job.progress_percent = 100.0
            elif job.status == "pending" and event_type != "created":
                job.status = "running"

        job_uuid = job.id if job else (uuid.UUID(job_id) if isinstance(job_id, str) else job_id)
        event = JobEvent(
            id=uuid.uuid4(),
            job_id=job_uuid,
            event_type=event_type,
            message=message,
            event_data=event_data or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_events(
        self,
        job_id: uuid.UUID | str,
        after_id: uuid.UUID | str | None = None,
    ) -> list[JobEvent]:
        """
        Retrieve chronological events for a job, optionally replaying after a given event_id.
        """
        job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
        stmt = (
            select(JobEvent)
            .where(JobEvent.job_id == job_uuid)
            .order_by(JobEvent.created_at.asc())
        )
        result = await self.session.execute(stmt)
        events = list(result.scalars().all())

        if after_id:
            after_uuid = uuid.UUID(after_id) if isinstance(after_id, str) else after_id
            for idx, ev in enumerate(events):
                if ev.id == after_uuid:
                    return events[idx + 1:]

        return events

    async def cancel_job(self, job_id: uuid.UUID | str) -> Job | None:
        """Mark a job as cancelled."""
        job = await self.get_by_id(job_id)
        if not job or job.status in ("completed", "failed"):
            return job

        job.status = "failed"
        job.error_message = "Job cancelled by operator."
        await self.emit_event(
            job_id=job.id,
            event_type="failed",
            message="Job cancelled by operator.",
        )
        return job
