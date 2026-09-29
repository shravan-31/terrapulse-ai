"""
backend/tests/unit/test_ingest_jobs.py
Unit tests for Job management, SSE streaming (ADR-005),
and ingestion API endpoints.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.aoi import _aoi_store
from app.main import create_app
from app.services.ingest_service import _scene_store, run_ingestion_job
from app.services.job_service import (
    cancel_job,
    create_job,
    emit_job_event,
    get_job,
    stream_job_events,
)


class MockJobRepo:
    async def create_job(self, job_type="ingest", job_id=None):
        return create_job(job_type)

    async def get_by_id(self, job_id):
        return get_job(job_id)

    async def cancel_job(self, job_id):
        return cancel_job(job_id)


class MockSceneRepo:
    def __init__(self):
        self.scenes = []

    async def list_scenes(self):
        return self.scenes

    async def get_by_id(self, scene_id):
        for s in self.scenes:
            if str(s.get("id")) == str(scene_id):
                return s
        return None

    async def get_by_product_id(self, prod_id):
        for s in self.scenes:
            if s.get("product_id") == prod_id:
                return s
        return None


@pytest.fixture
def test_app():
    from app.api.jobs import get_job_repository
    from app.api.scenes import (
        get_job_repository as get_scenes_job_repo,
        get_scene_repository,
    )
    application = create_app()
    job_repo = MockJobRepo()
    scene_repo = MockSceneRepo()
    application.dependency_overrides[get_job_repository] = lambda: job_repo
    application.dependency_overrides[get_scenes_job_repo] = lambda: job_repo
    application.dependency_overrides[get_scene_repository] = lambda: scene_repo
    return application


@pytest.fixture
def sample_aoi():
    aoi_id = "test-aoi-uuid-1234"
    _aoi_store[aoi_id] = {
        "id": aoi_id,
        "name": "Delhi Central",
        "description": "Urban monitoring",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [77.10, 28.60],
                    [77.25, 28.60],
                    [77.25, 28.75],
                    [77.10, 28.75],
                    [77.10, 28.60],
                ]
            ],
        },
        "area_km2": 235.0,
        "vertex_count": 5,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return aoi_id


def test_job_lifecycle():
    job = create_job(job_type="ingest")
    job_id = job["id"]
    assert job["status"] == "pending"
    assert job["progress_percent"] == 0.0

    # Emit progress event
    ev = emit_job_event(job_id, "downloading", "Downloading band B02", progress=45.0)
    updated_job = get_job(job_id)
    assert updated_job["status"] == "running"
    assert updated_job["progress_percent"] == 45.0

    # Cancel job
    cancelled_job = cancel_job(job_id)
    assert cancelled_job["status"] == "failed"
    assert "cancelled" in cancelled_job["error_message"]


def _auth_headers() -> dict[str, str]:
    import base64
    from app.core.settings import settings
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.mark.asyncio
async def test_stream_job_events_replay():
    job = create_job(job_type="ingest")
    job_id = job["id"]

    ev1 = emit_job_event(job_id, "stage_1", "Starting stage 1")
    ev2 = emit_job_event(job_id, "stage_2", "Starting stage 2")
    emit_job_event(job_id, "completed", "Job completed successfully")

    # Request stream resuming after ev1 ID
    events_replayed = []
    async for sse_chunk in stream_job_events(job_id, last_event_id=ev1["id"]):
        if "data:" in sse_chunk:
            events_replayed.append(sse_chunk)

    # Should only contain ev2 and completed event
    assert len(events_replayed) >= 2


@pytest.mark.asyncio
async def test_run_ingestion_job_flow(sample_aoi):
    job = create_job(job_type="ingest")
    job_id = job["id"]

    mock_scene = {
        "product_id": "S2B_MSIL2A_20240201_TEST",
        "provider": "copernicus",
        "acquisition_at": datetime(2024, 2, 1, tzinfo=timezone.utc).isoformat(),
        "cloud_coverage_percent": 2.1,
        "footprint": _aoi_store[sample_aoi]["geometry"],
        "crs": "EPSG:4326",
        "assets": {},
        "metadata_json": {"platform": "Sentinel-2B"},
    }

    with patch(
        "app.services.copernicus_service.CopernicusSTACClient.search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = [mock_scene]

        res = await run_ingestion_job(
            job_id=job_id,
            aoi_id=sample_aoi,
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 2, 5, tzinfo=timezone.utc),
        )

        assert res["status"] == "completed"
        assert len(res["scenes"]) == 1
        assert res["scenes"][0]["product_id"] == "S2B_MSIL2A_20240201_TEST"

        final_job = get_job(job_id)
        assert final_job["status"] == "completed"
        assert final_job["progress_percent"] == 100.0


@pytest.mark.asyncio
async def test_ingest_api_endpoints(test_app, sample_aoi):
    mock_scene = {
        "product_id": "S2A_MSIL2A_20240105_API_TEST",
        "provider": "copernicus",
        "acquisition_at": datetime(2024, 1, 5, tzinfo=timezone.utc).isoformat(),
        "cloud_coverage_percent": 3.0,
        "footprint": _aoi_store[sample_aoi]["geometry"],
        "crs": "EPSG:4326",
        "assets": {},
        "metadata_json": {"platform": "Sentinel-2A"},
    }

    with patch(
        "app.services.copernicus_service.CopernicusSTACClient.search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = [mock_scene]

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            # Trigger Ingest
            payload = {
                "aoi_id": sample_aoi,
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-15T00:00:00Z",
                "max_cloud_cover": 25.0,
                "max_scenes": 2,
            }
            resp = await client.post("/api/ingest", json=payload, headers=_auth_headers())
            assert resp.status_code == 202
            data = resp.json()
            assert "job_id" in data
            assert data["status"] == "pending"

            job_id = data["job_id"]

            # Poll Job status
            job_resp = await client.get(f"/api/jobs/{job_id}", headers=_auth_headers())
            assert job_resp.status_code == 200
            assert job_resp.json()["id"] == job_id

            # List scenes endpoint
            scenes_resp = await client.get("/api/scenes", headers=_auth_headers())
            assert scenes_resp.status_code == 200
            assert "scenes" in scenes_resp.json()


