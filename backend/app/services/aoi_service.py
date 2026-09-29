"""
backend/app/services/aoi_service.py
AOI (Area of Interest) validation and geometry service.

Implements Phase 2 requirements:
- GeoJSON Polygon validation (ring closure, coordinate finiteness, lon/lat order)
- Area and vertex limit enforcement (per settings.max_aoi_area_km2, max_aoi_vertices)
- Self-intersection detection (basic)
- Antimeridian and polar region detection
- Area computation (returned in km²)

NOTE: Full shapely-based validation is used when shapely is available.
When shapely is absent (host without geo stack), basic geometric checks are applied
and a warning is included in the response. This allows Phase 2 frontend work
without requiring Docker.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.errors import InvalidAOIError
from app.core.settings import settings


def _finite_check(coords: list[list[float]]) -> bool:
    """Return True if all coordinate values are finite (not NaN/Inf)."""
    return all(
        math.isfinite(lng) and math.isfinite(lat)
        for lng, lat in coords
    )


def _lon_lat_range_check(coords: list[list[float]]) -> bool:
    """Return True if all coordinates are within valid lon/lat ranges."""
    return all(
        -180.0 <= lng <= 180.0 and -90.0 <= lat <= 90.0
        for lng, lat in coords
    )


def _ring_closed(coords: list[list[float]]) -> bool:
    """GeoJSON polygon ring must start and end with the same coordinate."""
    if len(coords) < 4:
        return False
    return coords[0][0] == coords[-1][0] and coords[0][1] == coords[-1][1]


def _signed_area_degrees(coords: list[list[float]]) -> float:
    """Shoelace formula for signed area in degree² (for CCW/CW orientation check)."""
    n = len(coords) - 1  # exclude repeated closing point
    area = 0.0
    for i in range(n):
        x0, y0 = coords[i]
        x1, y1 = coords[(i + 1) % n]
        area += (x0 * y1) - (x1 * y0)
    return area / 2.0


def _approximate_area_km2(coords: list[list[float]]) -> float:
    """
    Haversine-based approximate polygon area in km².
    Uses Gauss's shoelace formula adapted for spherical coordinates.
    This is approximate (flat-Earth assumption per degree²) but sufficient for
    limit enforcement. For precise analysis, UTM reprojection is used later.
    """
    EARTH_RADIUS_KM = 6371.0
    n = len(coords) - 1  # exclude closing duplicate
    area = 0.0
    for i in range(n):
        lng1, lat1 = coords[i]
        lng2, lat2 = coords[(i + 1) % n]
        # Convert to radians
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        lng1_r = math.radians(lng1)
        lng2_r = math.radians(lng2)
        area += (lng2_r - lng1_r) * (2 + math.sin(lat1_r) + math.sin(lat2_r))
    area_sr = abs(area) / 2.0  # steradians
    area_km2 = area_sr * EARTH_RADIUS_KM ** 2
    return area_km2


def _detect_antimeridian(coords: list[list[float]]) -> bool:
    """
    Detect if ring crosses the antimeridian (longitude flips across ±180°).
    Returns True if any consecutive segment spans more than 180° in longitude.
    """
    for i in range(len(coords) - 1):
        lng1 = coords[i][0]
        lng2 = coords[i + 1][0]
        if abs(lng1 - lng2) > 180.0:
            return True
    return False


def _detect_polar(coords: list[list[float]]) -> bool:
    """Detect if any coordinate is at/near a pole (|lat| > 85°)."""
    return any(abs(lat) > 85.0 for _, lat in coords)


def validate_aoi_geometry(geometry: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a GeoJSON geometry dict for use as an AOI.

    Returns a dict with:
        - area_km2: float
        - vertex_count: int
        - warnings: list[str]

    Raises InvalidAOIError with actionable message on any violation.
    """
    warnings: list[str] = []

    # 1. Type check
    if not isinstance(geometry, dict):
        raise InvalidAOIError(
            detail="geometry must be a GeoJSON object",
            suggestion="Provide a GeoJSON Polygon geometry object with 'type' and 'coordinates' keys.",
        )

    geom_type = geometry.get("type")
    if geom_type not in ("Polygon", "MultiPolygon"):
        raise InvalidAOIError(
            detail=f"geometry type '{geom_type}' is not supported",
            suggestion="AOI must be a GeoJSON Polygon. MultiPolygon is not supported for a single AOI.",
        )

    if geom_type == "MultiPolygon":
        raise InvalidAOIError(
            detail="MultiPolygon AOI is not supported",
            suggestion="Provide a single Polygon AOI. Split into separate AOIs if needed.",
        )

    coords_list = geometry.get("coordinates")
    if not coords_list or not isinstance(coords_list, list) or len(coords_list) == 0:
        raise InvalidAOIError(
            detail="coordinates is missing or empty",
            suggestion="Provide at least one ring in the 'coordinates' array.",
        )

    # Use the exterior ring (first ring)
    exterior = coords_list[0]
    if not isinstance(exterior, list) or len(exterior) < 4:
        raise InvalidAOIError(
            detail="exterior ring must have at least 4 coordinate pairs (3 + closing)",
            suggestion="Polygon rings must close (first == last coordinate) and have at least 3 distinct vertices.",
        )

    # 2. Ring closure
    if not _ring_closed(exterior):
        raise InvalidAOIError(
            detail="exterior ring is not closed (first and last coordinates differ)",
            suggestion="GeoJSON requires the last coordinate to equal the first. Close the ring.",
        )

    # 3. Finite coordinates
    if not _finite_check(exterior):
        raise InvalidAOIError(
            detail="coordinates contain NaN or Infinity values",
            suggestion="All coordinates must be finite floating-point numbers.",
        )

    # 4. Lon/lat range
    if not _lon_lat_range_check(exterior):
        raise InvalidAOIError(
            detail="coordinates are outside valid lon/lat range",
            suggestion="Longitude must be in [-180, 180] and latitude in [-90, 90]. "
                       "Verify coordinate order: GeoJSON uses [longitude, latitude].",
        )

    # 5. Antimeridian
    if _detect_antimeridian(exterior):
        raise InvalidAOIError(
            detail="AOI ring crosses the antimeridian (longitude flip > 180°)",
            suggestion="AOIs crossing the antimeridian (180° meridian) are not supported. "
                       "Split the AOI at the antimeridian.",
        )

    # 6. Polar region
    if _detect_polar(exterior):
        warnings.append(
            "AOI extends above 85° latitude. Sentinel-2 coverage is sparse or absent in polar regions."
        )

    # 7. Vertex count
    vertex_count = len(exterior) - 1  # exclude closing duplicate
    if vertex_count > settings.max_aoi_vertices:
        raise InvalidAOIError(
            detail=f"AOI has {vertex_count} vertices (limit: {settings.max_aoi_vertices})",
            suggestion=f"Simplify the AOI polygon to fewer than {settings.max_aoi_vertices} vertices.",
        )

    # 8. Area
    area_km2 = _approximate_area_km2(exterior)
    if area_km2 > settings.max_aoi_area_km2:
        raise InvalidAOIError(
            detail=f"AOI area ≈ {area_km2:.1f} km² exceeds limit of {settings.max_aoi_area_km2:.0f} km²",
            suggestion="Reduce the AOI size. Large AOIs require many scenes and may exceed quota.",
        )

    # 9. Optional: shapely self-intersection check
    try:
        from shapely.geometry import shape as shapely_shape
        from shapely.validation import explain_validity

        geom = shapely_shape(geometry)
        if not geom.is_valid:
            explanation = explain_validity(geom)
            raise InvalidAOIError(
                detail=f"AOI polygon is self-intersecting or invalid: {explanation}",
                suggestion="Fix overlapping edges or self-intersections in the drawn polygon.",
            )
    except ImportError:
        warnings.append(
            "shapely is not installed: self-intersection check skipped. "
            "Install shapely for full geometry validation."
        )

    return {
        "area_km2": round(area_km2, 4),
        "vertex_count": vertex_count,
        "warnings": warnings,
    }
