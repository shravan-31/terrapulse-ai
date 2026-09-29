"""
backend/tests/unit/test_change_detection.py
Unit tests for Bi-Temporal Change Detection & Analyst Review (Phase 6, ADR-006, ADR-007).
"""

from __future__ import annotations

import base64
import uuid
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import settings
from app.main import create_app
from app.services.change_service import (
    bbox_to_geojson_polygon,
    filter_and_label_changes,
)


def _auth_headers() -> dict[str, str]:
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


def test_area_and_pixel_filter_adr006():
    """
    Verify ADR-006:
    Changes strictly smaller than 9 pixels OR 900 m² (for 10m pixels) must be rejected as noise.
    """
    mask = np.zeros((100, 100), dtype=bool)

    # Component 1: 2x2 = 4 pixels (below 9) -> must be rejected
    mask[10:12, 10:12] = True

    # Component 2: 4x4 = 16 pixels (above 9 pixels, 1600 m² > 900 m²) -> must be kept
    mask[50:54, 50:54] = True

    components = filter_and_label_changes(
        binary_mask=mask,
        pixel_resolution_m=10.0,
        min_pixels=9,
        min_area_m2=900.0,
    )

    assert len(components) == 1
    assert components[0]["pixel_count"] == 16
    assert components[0]["area_m2"] == 1600.0


def test_bbox_to_geojson_polygon_validity():
    """Verify polygonization generates closed 5-vertex GeoJSON Polygon in EPSG:4326."""
    tile_bounds = [77.1000, 28.6000, 77.2000, 28.7000]
    bbox = [10, 20, 50, 60]  # [r0, c0, r1, c1]
    poly = bbox_to_geojson_polygon(bbox, tile_bounds, image_shape=(256, 256))

    assert poly["type"] == "Polygon"
    coords = poly["coordinates"][0]
    assert len(coords) == 5  # Closed ring
    assert coords[0] == coords[-1]  # First vertex matches last vertex


@pytest.mark.asyncio
async def test_change_api_validation_errors():
    """Verify invalid UUID returns structured 422 ValidationError without traceback."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/change/analyze",
            json={
                "aoi_id": "invalid-uuid",
                "baseline_scene_id": str(uuid.uuid4()),
                "comparison_scene_id": str(uuid.uuid4()),
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "Invalid UUID" in data.get("error", "")


@pytest.mark.asyncio
async def test_review_decision_invalid_status_rejection():
    """Verify ADR-007 review status constraints."""
    app = create_app()
    fake_change_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/change/changes/{fake_change_id}/review",
            json={"review_status": "arbitrary_custom_status"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "Invalid review_status" in data.get("error", "")
