"""
backend/app/api/catalog.py
STAC-like spatial catalog endpoints (Section 43).

Endpoints:
- GET /api/catalog      — Retrieve catalog collection metadata and list items
- GET /api/catalog/{id} — Retrieve specific STAC item JSON document
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.catalog_service import (
    CATALOG_DIR,
    ensure_catalog_initialized,
    get_catalog_item,
    list_catalog_items,
)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("")
async def get_catalog(
    platform: Optional[str] = Query(None, description="Filter items by platform/sensor"),
    max_cloud: Optional[float] = Query(None, description="Max cloud cover %"),
    limit: int = Query(50, ge=1, le=200),
) -> JSONResponse:
    """Retrieve catalog collection summary and child STAC items."""
    ensure_catalog_initialized()

    collection_path = CATALOG_DIR / "collection.json"
    with open(collection_path, "r", encoding="utf-8") as f:
        col = json.load(f)

    items = list_catalog_items(platform=platform, max_cloud=max_cloud, limit=limit)
    col["features"] = items

    return JSONResponse(content=col)


@router.get("/{item_id}")
async def get_item(item_id: str) -> JSONResponse:
    """Retrieve specific STAC item JSON by ID."""
    item = get_catalog_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Catalog item '{item_id}' not found.")
    return JSONResponse(content=item)
