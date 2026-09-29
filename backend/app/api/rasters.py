"""
backend/app/api/rasters.py
Scene-specific raster delivery endpoints.

Implements ADR-008:
  GET /api/rasters/{asset_id}/tiles/{z}/{x}/{y}.png
  - Serves 256x256 RGBA PNG tiles directly from cached raster assets.
  - Transparent alpha for nodata / padding pixels.
  - SSRF guard: only controlled, registered asset IDs are reachable.
  - Cache-Control headers with long max-age (immutable versioned tiles).
  - Explicitly does NOT trigger ML inference.
"""

from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException, Response

from app.core.errors import InvalidAOIError, NotFoundError
from app.services.raster_service import get_raster_tile_png

router = APIRouter(prefix="/api/rasters", tags=["rasters"])

# Asset ID format guard: alphanumeric, dashes, underscores only
_ASSET_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")


@router.get("/{asset_id}/tiles/{z}/{x}/{y}.png")
async def get_tile_raster(
    asset_id: str,
    z: int,
    x: int,
    y: int,
) -> Response:
    """
    Retrieve a 256x256 PNG raster tile for client map display.
    """
    # SSRF guard on asset_id structure
    if not _ASSET_ID_REGEX.match(asset_id):
        raise NotFoundError(resource="RasterAsset", resource_id=asset_id)

    # Coordinate sanity checks
    if z < 0 or z > 24 or x < 0 or y < 0:
        raise HTTPException(status_code=400, detail="Invalid tile coordinates.")

    png_bytes = get_raster_tile_png(asset_id=asset_id, z=z, x=x, y=y)

    headers = {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=86400, immutable",
    }
    return Response(content=png_bytes, media_type="image/png", headers=headers)
