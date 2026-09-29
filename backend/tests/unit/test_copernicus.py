"""
backend/tests/unit/test_copernicus.py
Unit tests for Copernicus STAC discovery, OAuth2 token client,
and streaming download manager (ADR-009).
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.errors import (
    NoImageryError,
    QuotaExceededError,
    ResourceLimitError,
    UnauthorizedError,
    UpstreamFailureError,
)
from app.services.copernicus_service import (
    CopernicusAuth,
    CopernicusDownloadClient,
    CopernicusSTACClient,
)


@pytest.fixture
def mock_geometry():
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [77.0, 28.0],
                [77.1, 28.0],
                [77.1, 28.1],
                [77.0, 28.1],
                [77.0, 28.0],
            ]
        ],
    }


@pytest.mark.asyncio
async def test_copernicus_auth_success():
    auth = CopernicusAuth()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "access_token": "mock_token_12345",
        "expires_in": 3600,
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("app.services.copernicus_service.settings") as mock_settings:
        mock_settings.copernicus_client_id = "test_id"
        mock_settings.copernicus_client_secret = "test_secret"
        mock_settings.copernicus_token_url = "https://test.auth/token"

        token = await auth.get_token(client=mock_client)
        assert token == "mock_token_12345"
        # Second call within expiry should use cache without POSTing again
        token2 = await auth.get_token(client=mock_client)
        assert token2 == "mock_token_12345"
        assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_copernicus_auth_unauthorized():
    auth = CopernicusAuth()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.is_error = True

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp

    with patch("app.services.copernicus_service.settings") as mock_settings:
        mock_settings.copernicus_client_id = "bad_id"
        mock_settings.copernicus_client_secret = "bad_secret"
        mock_settings.copernicus_token_url = "https://test.auth/token"

        with pytest.raises(UnauthorizedError):
            await auth.get_token(client=mock_client)


@pytest.mark.asyncio
async def test_stac_search_success(mock_geometry):
    stac = CopernicusSTACClient()
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 15, tzinfo=timezone.utc)

    mock_features = [
        {
            "id": "S2A_MSIL2A_20240105T053211_N0510_R019_T43REQ_20240105T081234",
            "geometry": mock_geometry,
            "properties": {
                "datetime": "2024-01-05T05:32:11Z",
                "eo:cloud_cover": 4.5,
                "proj:epsg": 32643,
                "platform": "Sentinel-2A",
            },
            "assets": {"visual": {"href": "https://test.asset/visual.tif"}},
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {"features": mock_features}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        results = await stac.search(
            geometry=mock_geometry,
            start_date=start_date,
            end_date=end_date,
            max_cloud_cover=20.0,
        )

        assert len(results) == 1
        scene = results[0]
        assert scene["product_id"] == "S2A_MSIL2A_20240105T053211_N0510_R019_T43REQ_20240105T081234"
        assert scene["cloud_coverage_percent"] == 4.5
        assert scene["crs"] == "EPSG:32643"


@pytest.mark.asyncio
async def test_stac_search_no_imagery_raises(mock_geometry):
    stac = CopernicusSTACClient()
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 15, tzinfo=timezone.utc)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {"features": []}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(NoImageryError) as exc_info:
            await stac.search(
                geometry=mock_geometry,
                start_date=start_date,
                end_date=end_date,
                max_cloud_cover=10.0,
            )
        assert exc_info.value.code == "NO_IMAGERY"


@pytest.mark.asyncio
async def test_stac_search_quota_exceeded(mock_geometry):
    stac = CopernicusSTACClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "30"}
    mock_resp.is_error = True

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(QuotaExceededError) as exc_info:
            await stac.search(
                geometry=mock_geometry,
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
            )
        assert exc_info.value.code == "QUOTA_EXCEEDED"
        assert exc_info.value.extra.get("retry_after") == 30


@pytest.mark.asyncio
async def test_download_client_idempotent_cache_hit(tmp_path):
    dl_client = CopernicusDownloadClient()
    target_file = tmp_path / "scene_asset.tif"
    marker_file = tmp_path / "scene_asset.tif.complete"

    content = b"sample_raster_bytes"
    target_file.write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    marker_file.write_text(sha, encoding="utf-8")

    with patch("app.services.copernicus_service.settings") as mock_settings:
        mock_settings.cache_path = str(tmp_path)
        mock_settings.data_path = str(tmp_path)

        path, result_hash = await dl_client.download_asset(
            asset_url="https://test.copernicus.eu/asset.tif",
            target_path=target_file,
            auth_required=False,
        )

        assert path == target_file
        assert result_hash == sha


@pytest.mark.asyncio
async def test_download_client_path_traversal_guard(tmp_path):
    dl_client = CopernicusDownloadClient()
    traversal_path = tmp_path.parent / "escape.tif"

    with patch("app.services.copernicus_service.settings") as mock_settings:
        mock_settings.cache_path = str(tmp_path)
        mock_settings.data_path = str(tmp_path)

        with pytest.raises(ValueError, match="outside allowed"):
            await dl_client.download_asset(
                asset_url="https://test/asset.tif",
                target_path=traversal_path,
                auth_required=False,
            )
