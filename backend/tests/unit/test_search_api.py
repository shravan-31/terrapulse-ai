"""
backend/tests/unit/test_search_api.py
Unit and endpoint tests for Semantic Search & Visual Similarity (Phase 5, ADR-004).
"""

from __future__ import annotations

import base64
import io
import uuid
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.settings import settings
from app.main import create_app
from app.services.faiss_service import get_index_manager


def _auth_headers() -> dict[str, str]:
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.mark.asyncio
async def test_semantic_search_empty_index():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/search/semantic",
            json={"query": "new industrial construction near highway", "top_k": 5},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["count"] == 0
        assert data["completeness"] == "exact"


@pytest.mark.asyncio
async def test_image_search_size_limit_rejection():
    app = create_app()
    # Create fake oversized byte buffer (>10MB)
    fake_huge_bytes = b"0" * (11 * 1024 * 1024)
    files = {"file": ("huge_image.png", io.BytesIO(fake_huge_bytes), "image/png")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/search/image",
            files=files,
            headers=_auth_headers(),
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "10MB" in data.get("error", "")


@pytest.mark.asyncio
async def test_similar_tiles_nonexistent_404():
    app = create_app()
    random_tile_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/api/search/similar/{random_tile_id}",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404
