"""
backend/app/api/imagery.py
Satellite Imagery discovery and inspection endpoints (Section 43).

Endpoints:
- GET /api/imagery      — List all ingested satellite scenes and footprints
- GET /api/imagery/{id} — Retrieve scene metadata, bounding box, bands, and tiles
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.scene_repository import SceneRepository
from app.services.catalog_service import list_catalog_items, get_catalog_item

router = APIRouter(prefix="/api/imagery", tags=["imagery"])


@router.get("")
async def list_imagery(
    platform: Optional[str] = Query(None, description="Filter by sensor platform"),
    max_cloud: Optional[float] = Query(None, description="Max cloud coverage percentage"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    List all ingested satellite scenes with geospatial footprints and acquisition dates.
    Combines database records and local STAC catalog items.
    """
    catalog_items = list_catalog_items(platform=platform, max_cloud=max_cloud, limit=limit)

    results: List[dict[str, Any]] = []
    for item in catalog_items:
        props = item.get("properties", {})
        results.append({
            "id": item.get("id"),
            "sensor": props.get("platform", "Sentinel-2"),
            "acquisition_date": props.get("datetime", ""),
            "bbox": item.get("bbox", []),
            "geometry": item.get("geometry", {}),
            "cloud_percentage": props.get("eo:cloud_cover", 0.0),
            "crs": props.get("proj:epsg", "EPSG:4326"),
            "resolution_m": props.get("gsd", 10.0),
            "tile_count": props.get("tile_count", 0),
            "thumbnail_url": f"/api/rasters/{item.get('id')}/thumbnail.png",
        })

    # Also query PostgreSQL if scenes exist
    try:
        scene_repo = SceneRepository(db)
        db_scenes = await scene_repo.list_scenes()
        for s in db_scenes:
            if not any(r["id"] == str(s.id) or r["id"] == s.product_id for r in results):
                results.append({
                    "id": str(s.id),
                    "sensor": s.provider,
                    "acquisition_date": s.acquisition_at.isoformat() if hasattr(s.acquisition_at, "isoformat") else str(s.acquisition_at),
                    "bbox": [s.footprint.get("bbox", [])] if isinstance(s.footprint, dict) else [],
                    "geometry": s.footprint,
                    "cloud_percentage": s.cloud_coverage_percent,
                    "crs": s.crs,
                    "resolution_m": 10.0,
                    "thumbnail_url": f"/api/rasters/{s.id}/thumbnail.png",
                })
    except Exception:
        pass

    return JSONResponse(
        content={
            "imagery": results,
            "count": len(results),
        }
    )


@router.get("/{image_id}")
async def get_imagery_details(
    image_id: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Retrieve full metadata for a specific satellite scene."""
    item = get_catalog_item(image_id)
    if item:
        return JSONResponse(content=item)

    # Check database
    try:
        scene_repo = SceneRepository(db)
        scene = await scene_repo.get_by_id(image_id)
        if scene:
            return JSONResponse(
                content={
                    "id": str(scene.id),
                    "product_id": scene.product_id,
                    "sensor": scene.provider,
                    "acquisition_date": scene.acquisition_at.isoformat(),
                    "cloud_coverage_percent": scene.cloud_coverage_percent,
                    "footprint": scene.footprint,
                    "crs": scene.crs,
                    "metadata": scene.metadata_json,
                }
            )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Imagery with id '{image_id}' not found.")
