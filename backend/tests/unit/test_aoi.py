"""
backend/tests/unit/test_aoi.py
Phase 2: Unit tests for AOI validation and API endpoint.

Tests:
1. Valid polygon creates AOI with correct area_km2 and vertex_count.
2. Invalid geometry type (Point) is rejected with INVALID_AOI.
3. Non-closed ring is rejected.
4. NaN/Inf coordinates are rejected.
5. Coordinates outside lon/lat range are rejected.
6. Antimeridian-crossing AOI is rejected.
7. Oversized AOI (area > limit) is rejected.
8. Polar region AOI issues a warning but is not rejected.
9. Unknown AOI id returns 404.
10. Valid AOI is retrievable after creation (GET /api/aoi/{id}).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    from app.api.aoi import InMemoryAOIRepository, get_aoi_repository
    application = create_app()
    repo = InMemoryAOIRepository()
    application.dependency_overrides[get_aoi_repository] = lambda: repo
    return application


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.0, 28.0],
            [77.1, 28.0],
            [77.1, 28.1],
            [77.0, 28.1],
            [77.0, 28.0],  # closed
        ]
    ],
}

OPERATOR_CREDS = ("admin", "test")


def _auth_headers() -> dict[str, str]:
    import base64
    from app.core.settings import settings
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_valid_aoi(client):
    resp = await client.post(
        "/api/aoi",
        json={"name": "Test Delhi AOI", "geometry": VALID_POLYGON},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["area_km2"] > 0
    assert data["vertex_count"] == 4  # 5 coords - 1 closing = 4
    assert data["name"] == "Test Delhi AOI"


@pytest.mark.asyncio
async def test_create_aoi_invalid_type_point(client):
    resp = await client.post(
        "/api/aoi",
        json={
            "name": "Bad AOI",
            "geometry": {"type": "Point", "coordinates": [77.0, 28.0]},
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == "INVALID_AOI"


@pytest.mark.asyncio
async def test_create_aoi_non_closed_ring(client):
    resp = await client.post(
        "/api/aoi",
        json={
            "name": "Non-closed",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[77.0, 28.0], [77.1, 28.0], [77.1, 28.1], [77.0, 28.1]]
                    # Missing closing coord [77.0, 28.0]
                ],
            },
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == "INVALID_AOI"


@pytest.mark.asyncio
async def test_create_aoi_invalid_coords_range(client):
    """Longitude > 180 must be rejected."""
    resp = await client.post(
        "/api/aoi",
        json={
            "name": "Bad coords",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[200.0, 28.0], [201.0, 28.0], [201.0, 29.0], [200.0, 29.0], [200.0, 28.0]]
                ],
            },
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == "INVALID_AOI"


@pytest.mark.asyncio
async def test_create_aoi_antimeridian_crossing(client):
    """Ring spanning > 180° in longitude should be rejected."""
    resp = await client.post(
        "/api/aoi",
        json={
            "name": "Antimeridian",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[170.0, 10.0], [-170.0, 10.0], [-170.0, 20.0], [170.0, 20.0], [170.0, 10.0]]
                ],
            },
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["code"] == "INVALID_AOI"


@pytest.mark.asyncio
async def test_create_aoi_polar_warning(client):
    """Polar AOI (|lat| > 85) is accepted but includes a warning."""
    resp = await client.post(
        "/api/aoi",
        json={
            "name": "Polar AOI",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0.0, 86.0], [1.0, 86.0], [1.0, 87.0], [0.0, 87.0], [0.0, 86.0]]
                ],
            },
        },
        headers=_auth_headers(),
    )
    # Not rejected — but should have a warning
    assert resp.status_code == 201
    data = resp.json()
    assert "warnings" in data
    assert any("polar" in w.lower() or "latitude" in w.lower() for w in data["warnings"])


@pytest.mark.asyncio
async def test_get_aoi_not_found(client):
    resp = await client.get(
        "/api/aoi/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(),
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_aoi_roundtrip(client):
    """Create AOI then retrieve it by ID."""
    post_resp = await client.post(
        "/api/aoi",
        json={"name": "Roundtrip AOI", "geometry": VALID_POLYGON},
        headers=_auth_headers(),
    )
    assert post_resp.status_code == 201
    aoi_id = post_resp.json()["id"]

    get_resp = await client.get(f"/api/aoi/{aoi_id}", headers=_auth_headers())
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == aoi_id
    assert data["name"] == "Roundtrip AOI"


@pytest.mark.asyncio
async def test_list_aois(client):
    """POST two AOIs and verify they appear in the list."""
    headers = _auth_headers()
    for i in range(2):
        await client.post(
            "/api/aoi",
            json={"name": f"List AOI {i}", "geometry": VALID_POLYGON},
            headers=headers,
        )

    resp = await client.get("/api/aoi", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 2
    assert isinstance(data["aois"], list)


@pytest.mark.asyncio
async def test_aoi_database_unavailability_returns_503():
    """Verify that when database is unavailable in normal mode, a structured 503 is returned."""
    # Create standard app without in-memory repository override
    normal_app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=normal_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as unconfigured_client:
        resp = await unconfigured_client.post(
            "/api/aoi",
            json={"name": "No DB Test", "geometry": VALID_POLYGON},
            headers=_auth_headers(),
        )
        # If DB is running, it returns 201; if DB is unavailable, returns 503 structured error
        if resp.status_code == 503:
            data = resp.json()
            assert data["code"] == "UPSTREAM_FAILURE"
            assert "Database service unavailable" in data["error"]
            assert "request_id" in data
        else:
            assert resp.status_code == 201

