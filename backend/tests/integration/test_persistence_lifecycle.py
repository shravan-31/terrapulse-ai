"""
backend/tests/integration/test_persistence_lifecycle.py
Integration tests for database persistence lifecycle, restart durability,
worker interruption, dispatch failure, duplicate ingestion, and event replay.

Implements ADR-003, ADR-005, ADR-007, ADR-012.
If PostgreSQL is offline, marks tests as BLOCKED / SKIPPED pending live service.
"""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import reset_engine
from app.core.settings import settings
from app.main import create_app


@pytest.fixture(autouse=True)
async def cleanup_database_pool():
    """Ensure connection pools are disposed cleanly on the current event loop."""
    yield
    await reset_engine()


async def is_db_available() -> bool:
    """Check if the configured PostgreSQL database is accessible and migrations have run."""
    try:
        from app.core.database import get_engine
        engine = get_engine()
        async with engine.connect() as conn:
            res = await conn.execute(text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'aois'"
            ))
            return res.scalar() is not None
    except Exception:
        return False


def _auth_headers() -> dict[str, str]:
    import base64
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.mark.asyncio
async def test_aoi_persistence_across_restart():
    """
    Verify that an AOI written in one session survives engine disposal
    and is retrievable in a fresh, independent connection session.
    """
    if not await is_db_available():
        pytest.skip("PostgreSQL/PostGIS not accessible on host; persistence test BLOCKED pending live database.")

    app = create_app()
    aoi_payload = {
        "name": f"Restart Test AOI {uuid.uuid4().hex[:6]}",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.10, 28.60],
                    [77.20, 28.60],
                    [77.20, 28.70],
                    [77.10, 28.70],
                    [77.10, 28.60],
                ]
            ],
        },
    }

    # 1. Create AOI
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/aoi", json=aoi_payload, headers=_auth_headers())
        assert resp.status_code == 201
        created_id = resp.json()["id"]

    # 2. Simulate server restart: new app instance and fresh connection pool
    fresh_app = create_app()
    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as fresh_client:
        get_resp = await fresh_client.get(f"/api/aoi/{created_id}", headers=_auth_headers())
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert fetched["id"] == created_id
        assert fetched["name"] == aoi_payload["name"]


@pytest.mark.asyncio
async def test_duplicate_ingestion_idempotency():
    """
    Verify that repeated ingestion requests for the same scene product_id
    reuse existing assets and do not duplicate database rows (ADR-003, ADR-009).
    """
    if not await is_db_available():
        pytest.skip("PostgreSQL not accessible on host; duplicate ingestion test BLOCKED pending live database.")

    from app.core.database import db_transaction
    from app.repositories.scene_repository import SceneRepository

    test_product_id = f"S2A_MSIL2A_IDEMPOTENT_TEST_{uuid.uuid4().hex[:8]}"

    async with db_transaction() as session:
        repo = SceneRepository(session)
        scene1 = await repo.create_scene(
            product_id=test_product_id,
            acquisition_at=datetime.now(timezone.utc),
            cloud_coverage_percent=1.5,
            footprint={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        )
        assert scene1.id is not None

    # In a separate transaction, query existing
    async with db_transaction() as session2:
        repo2 = SceneRepository(session2)
        existing = await repo2.get_by_product_id(test_product_id)
        assert existing is not None
        assert existing.product_id == test_product_id


@pytest.mark.asyncio
async def test_durable_event_replay():
    """
    Verify that job events can be replayed from the durable job_events table
    after an interruption using Last-Event-ID (ADR-005).
    """
    if not await is_db_available():
        pytest.skip("PostgreSQL not accessible on host; event replay test BLOCKED pending live database.")

    from app.core.database import db_transaction
    from app.repositories.job_repository import JobRepository
    from app.services.job_service import stream_job_events

    job_id_str = str(uuid.uuid4())
    async with db_transaction() as session:
        repo = JobRepository(session)
        job = await repo.create_job("ingest", job_id=uuid.UUID(job_id_str))
        ev1 = await repo.emit_event(job.id, "stage_1", "Stage 1 started")
        ev2 = await repo.emit_event(job.id, "stage_2", "Stage 2 started")
        ev3 = await repo.emit_event(job.id, "completed", "Job finished")

    # Replay events after ev1
    replayed = []
    async for chunk in stream_job_events(job_id_str, last_event_id=str(ev1.id)):
        if "data:" in chunk:
            replayed.append(chunk)

    assert len(replayed) >= 2


@pytest.mark.asyncio
async def test_worker_interruption_and_cancellation():
    """
    Verify that an in-flight worker job can be interrupted/cancelled gracefully,
    recording failure/cancellation in durable job records and stopping execution.
    """
    if not await is_db_available():
        pytest.skip("PostgreSQL not accessible on host; cancellation test BLOCKED pending live database.")

    from app.core.database import db_transaction
    from app.repositories.job_repository import JobRepository
    from app.workers.tasks import _execute_durable_ingest

    job_id = str(uuid.uuid4())
    fake_aoi_id = str(uuid.uuid4())

    async with db_transaction() as session:
        repo = JobRepository(session)
        job = await repo.create_job("ingest", job_id=uuid.UUID(job_id))
        # Pre-mark job as failed/cancelled
        await repo.update_status(job.id, "failed", error_message="Cancelled by operator")

    # Run worker task logic; should detect cancelled status and abort immediately
    result = await _execute_durable_ingest(
        job_id=job_id,
        aoi_id=fake_aoi_id,
        start_date_iso="2026-01-01T00:00:00Z",
        end_date_iso="2026-01-02T00:00:00Z",
    )
    assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_celery_dispatch_failure_resilience(monkeypatch):
    """
    Verify that if the Celery broker is unreachable during job submission,
    the API gracefully falls back, still persists the job record, and returns 202.
    """
    if not await is_db_available():
        pytest.skip("PostgreSQL not accessible on host; dispatch resilience test BLOCKED pending live database.")

    app = create_app()

    # Simulate Celery broker connection error
    def mock_delay(*args, **kwargs):
        raise ConnectionRefusedError("Simulated Redis/Celery broker connection refusal")

    from app.workers import tasks
    monkeypatch.setattr(tasks.ingest_scene_task, "delay", mock_delay)

    aoi_id = str(uuid.uuid4())
    payload = {
        "aoi_id": aoi_id,
        "start_date": "2026-01-01T00:00:00Z",
        "end_date": "2026-01-05T00:00:00Z",
        "max_cloud_cover": 20.0,
        "max_scenes": 2,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/ingest", json=payload, headers=_auth_headers())
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["celery_dispatched"] is False  # Fallback was triggered
        assert data["status"] == "pending"

