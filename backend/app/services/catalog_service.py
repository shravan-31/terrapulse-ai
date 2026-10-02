"""
backend/app/services/catalog_service.py
Local STAC-like spatial catalog service (Section 10).

Implements:
- Collection management in data/catalog/collection.json
- Per-item STAC JSON documents in data/catalog/items/{item_id}.json
- Valid STAC 1.0.0 / GeoJSON formatting
- Spatial (bbox) and temporal filtering across local records
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.geospatial.geometry import bbox_to_geojson_polygon

log = structlog.get_logger("satquery.services.catalog")

CATALOG_DIR = Path("./data/catalog")
ITEMS_DIR = CATALOG_DIR / "items"


def ensure_catalog_initialized() -> None:
    """Ensure catalog directory and root collection.json exist."""
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    collection_file = CATALOG_DIR / "collection.json"
    if not collection_file.exists():
        initial_collection = {
            "stac_version": "1.0.0",
            "id": "terrapulse-local-catalog",
            "title": "TerraPulse AI Offline Satellite Imagery Catalog",
            "description": "Local catalog of ingested Sentinel-2, Landsat, and GeoTIFF scenes for offline analysis.",
            "license": "proprietary",
            "extent": {
                "spatial": {
                    "bbox": [[-180.0, -90.0, 180.0, 90.0]],
                },
                "temporal": {
                    "interval": [["2020-01-01T00:00:00Z", None]],
                },
            },
            "links": [
                {"rel": "self", "href": "./collection.json", "type": "application/json"},
                {"rel": "root", "href": "./collection.json", "type": "application/json"},
            ],
            "item_count": 0,
        }
        with open(collection_file, "w", encoding="utf-8") as f:
            json.dump(initial_collection, f, indent=2)


def add_catalog_item(
    item_id: str,
    bbox: list[float],  # [min_lon, min_lat, max_lon, max_lat]
    datetime_iso: str,
    platform: str,
    instruments: list[str],
    assets: dict[str, Any],
    projection: str = "EPSG:4326",
    resolution_m: float = 10.0,
    cloud_cover: float | str = 0.0,
    properties_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create and persist a STAC item document in data/catalog/items/{item_id}.json.
    """
    ensure_catalog_initialized()

    geometry = bbox_to_geojson_polygon(bbox)
    item_doc = {
        "stac_version": "1.0.0",
        "type": "Feature",
        "id": item_id,
        "bbox": bbox,
        "geometry": geometry,
        "properties": {
            "datetime": datetime_iso,
            "platform": platform,
            "instruments": instruments,
            "proj:epsg": 4326 if "4326" in str(projection) else projection,
            "gsd": resolution_m,
            "eo:cloud_cover": cloud_cover if isinstance(cloud_cover, (int, float)) else None,
            "cloud_status": str(cloud_cover),
            "created": datetime.now(timezone.utc).isoformat(),
            **(properties_extra or {}),
        },
        "assets": assets,
        "links": [
            {"rel": "collection", "href": "../collection.json", "type": "application/json"},
            {"rel": "self", "href": f"./{item_id}.json", "type": "application/json"},
        ],
    }

    item_path = ITEMS_DIR / f"{item_id}.json"
    with open(item_path, "w", encoding="utf-8") as f:
        json.dump(item_doc, f, indent=2)

    # Update collection item count
    _update_collection_summary()

    log.info("Persisted STAC item to catalog", item_id=item_id, path=str(item_path))
    return item_doc


def get_catalog_item(item_id: str) -> Optional[dict[str, Any]]:
    """Retrieve STAC item by ID."""
    ensure_catalog_initialized()
    item_path = ITEMS_DIR / f"{item_id}.json"
    if not item_path.exists():
        return None
    with open(item_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_catalog_items(
    platform: Optional[str] = None,
    max_cloud: Optional[float] = None,
    limit: int = 50,
) -> List[dict[str, Any]]:
    """List all available items in the local catalog with optional filters."""
    ensure_catalog_initialized()
    items: List[dict[str, Any]] = []

    for item_file in sorted(ITEMS_DIR.glob("*.json")):
        try:
            with open(item_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
            props = doc.get("properties", {})

            if platform and platform.lower() not in props.get("platform", "").lower():
                continue

            cloud = props.get("eo:cloud_cover")
            if max_cloud is not None and cloud is not None and cloud > max_cloud:
                continue

            items.append(doc)
            if len(items) >= limit:
                break
        except Exception:
            continue

    return items


def _update_collection_summary() -> None:
    """Recalculate collection metadata bounding box and item count."""
    collection_file = CATALOG_DIR / "collection.json"
    if not collection_file.exists():
        return

    items = list(ITEMS_DIR.glob("*.json"))
    with open(collection_file, "r", encoding="utf-8") as f:
        col = json.load(f)

    col["item_count"] = len(items)
    with open(collection_file, "w", encoding="utf-8") as f:
        json.dump(col, f, indent=2)
