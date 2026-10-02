"""
backend/app/api/changes.py
Bi-temporal satellite change detection endpoints (Section 43).

Endpoints:
- POST /api/change-detection — Execute change detection between before & after imagery
- GET  /api/change-detection/{id} — Retrieve detection mask, overlay, and polygons
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import cv2
import numpy as np
from PIL import Image
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.geospatial.alignment import align_temporal_images
from app.geospatial.geometry import create_feature_collection
from app.geospatial.raster import read_raster
from app.ml.change_detection import get_change_detector

log = structlog.get_logger("satquery.api.change_detection")

router = APIRouter(prefix="/api/change-detection", tags=["change-detection"])

# Local persistence cache for change detection results
_DETECTION_RESULTS: Dict[str, Dict[str, Any]] = {}
MASKS_DIR = Path("./data/masks")


class ChangeDetectionRequest(BaseModel):
    before_image_path: str = Field(..., description="Filepath or UUID of baseline raster")
    after_image_path: str = Field(..., description="Filepath or UUID of comparison raster")
    method: Literal["classical", "deep"] = Field("classical", description="Change detection method")
    threshold: float = Field(0.55, ge=0.1, le=0.99, description="Change probability threshold")
    min_change_area: float = Field(900.0, ge=10.0, description="Minimum change area in m2")
    pixel_resolution_m: float = Field(10.0, ge=0.5, le=100.0)


@router.post("")
async def execute_change_detection(
    req: ChangeDetectionRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Run bi-temporal change detection pipeline:
    1. Read and validate images
    2. Temporal co-registration (OpenCV)
    3. Method A (Classical) or Method B (Deep Learning) change detection
    4. Connected components, area calculations, evidence-based classification
    5. Save change mask & overlay
    """
    detection_id = str(uuid.uuid4())
    p_before = Path(req.before_image_path)
    p_after = Path(req.after_image_path)

    if not p_before.exists() or not p_after.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Image paths not found: before={p_before.exists()}, after={p_after.exists()}",
        )

    # 1. Read imagery
    img_before, meta_before = read_raster(p_before)
    img_after, meta_after = read_raster(p_after)

    # 2. Temporal Co-Registration / Alignment
    alignment = align_temporal_images(img_before, img_after, max_acceptable_shift_px=3.0)
    aligned_after = alignment.aligned_target

    # 3. Change Detection
    detector = get_change_detector(method=req.method)
    result = detector.detect_changes(
        t1_image=img_before,
        t2_image=aligned_after,
        pixel_resolution_m=req.pixel_resolution_m,
        threshold=req.threshold,
        min_area_m2=req.min_change_area,
        geotransform=meta_before.geotransform,
    )

    # 4. Save visual masks
    MASKS_DIR.mkdir(parents=True, exist_ok=True)
    mask_file = MASKS_DIR / f"{detection_id}_change_mask.png"
    overlay_file = MASKS_DIR / f"{detection_id}_change_overlay.png"

    Image.fromarray((result.change_mask.astype(np.uint8) * 255)).save(mask_file, format="PNG")
    Image.fromarray(result.change_overlay).save(overlay_file, format="PNG")

    # 5. Build GeoJSON FeatureCollection
    features = []
    for comp in result.components:
        features.append({
            "type": "Feature",
            "geometry": comp.polygon,
            "properties": {
                "change_type": comp.change_type,
                "area_m2": comp.area_m2,
                "area_ha": round(comp.area_m2 / 10000.0, 4),
                "confidence": comp.confidence,
                "pixel_count": comp.pixel_count,
                "bbox_pixel": comp.bbox_pixel,
                "spectral_delta": comp.spectral_delta,
            },
        })

    geojson_fc = create_feature_collection(
        features=features,
        metadata={
            "detection_id": detection_id,
            "methodology": result.methodology,
            "primary_change_type": result.primary_change_type,
            "total_change_area_m2": result.total_change_area_m2,
            "percentage_change": result.percentage_change,
            "overall_confidence": result.overall_confidence,
            "alignment_status": alignment.status,
            "alignment_shift_pixels": alignment.shift_pixels,
        },
    )

    response_data = {
        "detection_id": detection_id,
        "status": "COMPLETED",
        "methodology": result.methodology,
        "alignment": {
            "status": alignment.status,
            "shift_pixels": alignment.shift_pixels,
            "correlation_score": alignment.correlation_score,
            "inliers": alignment.inlier_count,
        },
        "metrics": {
            "total_change_area_m2": result.total_change_area_m2,
            "total_change_area_ha": round(result.total_change_area_m2 / 10000.0, 2),
            "percentage_change": result.percentage_change,
            "overall_confidence": result.overall_confidence,
            "primary_change_type": result.primary_change_type,
            "components_count": len(result.components),
        },
        "paths": {
            "before_image": str(p_before),
            "after_image": str(p_after),
            "mask_path": str(mask_file),
            "overlay_path": str(overlay_file),
        },
        "geojson": geojson_fc,
    }

    # Cache for later retrieval
    _DETECTION_RESULTS[detection_id] = response_data
    log.info("Change detection executed successfully", detection_id=detection_id, change_area=result.total_change_area_m2)

    return JSONResponse(status_code=200, content=response_data)


@router.get("/{detection_id}")
async def get_change_detection(detection_id: str) -> JSONResponse:
    """Retrieve details and polygons of a previously executed change detection."""
    record = _DETECTION_RESULTS.get(detection_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Change detection record '{detection_id}' not found.")
    return JSONResponse(content=record)
