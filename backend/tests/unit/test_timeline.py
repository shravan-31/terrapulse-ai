"""
backend/tests/unit/test_timeline.py
Unit tests for multi-temporal timeline analysis and spectral hypothesis classification (Phase 7, Phase 8, ADR-007).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import settings
from app.main import create_app
from app.services.timeline_service import (
    classify_change_hypothesis,
    evaluate_temporal_lifecycle,
)


def _auth_headers() -> dict[str, str]:
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


def test_temporal_lifecycle_rules_adr007():
    """
    Verify ADR-007 temporal lifecycle status rules:
    - Candidate: single observation detection
    - Confirmed: detected in subsequent independent acquisition
    - Inconsistent: detected then absent in subsequent cloud-free acquisition
    """
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 5, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 10, tzinfo=timezone.utc)

    # 1. Candidate sequence: Baseline -> Detected
    res_candidate = evaluate_temporal_lifecycle([
        {"timestamp": t0, "detected": False, "cloud_cover": 0.0, "is_independent": True},
        {"timestamp": t1, "detected": True, "cloud_cover": 0.0, "is_independent": True},
    ])
    assert res_candidate["temporal_status"] == "candidate"
    assert res_candidate["last_baseline_observation_at"] == t0.isoformat()
    assert res_candidate["earliest_supported_at"] == t1.isoformat()
    assert res_candidate["confirmed_at"] is None
    assert res_candidate["left_censored"] is True

    # 2. Confirmed sequence: Baseline -> Detected -> Detected in independent overpass
    res_confirmed = evaluate_temporal_lifecycle([
        {"timestamp": t0, "detected": False, "cloud_cover": 0.0, "is_independent": True},
        {"timestamp": t1, "detected": True, "cloud_cover": 0.0, "is_independent": True},
        {"timestamp": t2, "detected": True, "cloud_cover": 0.0, "is_independent": True},
    ])
    assert res_confirmed["temporal_status"] == "confirmed"
    assert res_confirmed["confirmed_at"] == t2.isoformat()

    # 3. Inconsistent (flicker): Detected -> Absent in clear scene
    res_inconsistent = evaluate_temporal_lifecycle([
        {"timestamp": t0, "detected": False, "cloud_cover": 0.0, "is_independent": True},
        {"timestamp": t1, "detected": True, "cloud_cover": 0.0, "is_independent": True},
        {"timestamp": t2, "detected": False, "cloud_cover": 5.0, "is_independent": True},
    ])
    assert res_inconsistent["temporal_status"] == "inconsistent"


def test_spectral_change_classification_hypotheses():
    """Verify spectral delta hypotheses per Phase 8."""
    # Vegetation clearance: NDVI drop
    hyp_veg = classify_change_hypothesis(ndvi_delta=-0.35, aspect_ratio=1.2)
    assert hyp_veg["change_type"] == "vegetation_land_cover"
    assert hyp_veg["change_kind"] == "disappearance"

    # Construction: NDBI rise + compact geometry
    hyp_const = classify_change_hypothesis(ndbi_delta=0.25, aspect_ratio=1.5)
    assert hyp_const["change_type"] == "construction"
    assert hyp_const["change_kind"] == "appearance"

    # Road development: elongated feature with NDBI rise
    hyp_road = classify_change_hypothesis(ndbi_delta=0.10, aspect_ratio=4.0)
    assert hyp_road["change_type"] == "road_development"

    # Water variation
    hyp_water = classify_change_hypothesis(ndwi_delta=0.30, aspect_ratio=1.0)
    assert hyp_water["change_type"] == "water_variation"
    assert hyp_water["change_kind"] == "expansion"


@pytest.mark.asyncio
async def test_timeline_endpoints():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. GET /api/timeline
        resp_get = await client.get("/api/timeline", headers=_auth_headers())
        assert resp_get.status_code == 200
        data_get = resp_get.json()
        assert "nodes" in data_get

        # 2. POST /api/timeline/evaluate
        payload = {
            "observations": [
                {"timestamp": "2026-01-01T00:00:00Z", "detected": False, "cloud_cover": 0.0, "is_independent": True},
                {"timestamp": "2026-01-05T00:00:00Z", "detected": True, "cloud_cover": 0.0, "is_independent": True},
            ]
        }
        resp_post = await client.post("/api/timeline/evaluate", json=payload, headers=_auth_headers())
        assert resp_post.status_code == 200
        data_post = resp_post.json()
        assert data_post["temporal_status"] == "candidate"
        assert data_post["left_censored"] is True
