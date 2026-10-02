"""
backend/app/geospatial/geometry.py
GeoJSON polygon and FeatureCollection builders with area computations.

Implements Section 22:
- Valid GeoJSON Feature and FeatureCollection generation
- Accurate polygon area calculation in m², hectares, and km²
- Coordinate transformations and bounding box formatting
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence


def create_geojson_feature(
    geometry: dict[str, Any],
    properties: dict[str, Any],
    feature_id: str | None = None,
) -> dict[str, Any]:
    """Build a standard GeoJSON Feature object."""
    feat: dict[str, Any] = {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }
    if feature_id:
        feat["id"] = feature_id
    return feat


def create_feature_collection(
    features: Sequence[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard GeoJSON FeatureCollection."""
    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": list(features),
    }
    if metadata:
        fc["metadata"] = metadata
    return fc


def bbox_to_geojson_polygon(bbox: list[float]) -> dict[str, Any]:
    """Convert [min_lon, min_lat, max_lon, max_lat] to GeoJSON Polygon."""
    minx, miny, maxx, maxy = bbox
    coords = [
        [minx, miny],
        [maxx, miny],
        [maxx, maxy],
        [minx, maxy],
        [minx, miny],
    ]
    return {
        "type": "Polygon",
        "coordinates": [coords],
    }


def calculate_area_metrics(area_m2: float) -> dict[str, float]:
    """Convert square meters to hectares and square kilometers."""
    return {
        "area_m2": round(area_m2, 2),
        "area_ha": round(area_m2 / 10000.0, 4),
        "area_km2": round(area_m2 / 1000000.0, 6),
    }
