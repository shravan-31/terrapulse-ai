"""
backend/app/workers/celery_app.py
Celery application instance configuration for asynchronous worker tasks.
"""

from __future__ import annotations

from celery import Celery

from app.core.settings import settings

celery_app = Celery(
    "satquery",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.job_time_limit_s,
    worker_concurrency=settings.worker_concurrency,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
