"""
backend/app/api/timeline.py
Satellite timeline and multi-temporal lifecycle API endpoints (Phase 7, Phase 8, ADR-007).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.timeline_service import (
    classify_change_hypothesis,
    evaluate_temporal_lifecycle,
    fetch_aoi_timeline,
)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


class ObservationItem(BaseModel):
    timestamp: str = Field(..., description="ISO 8601 acquisition timestamp")
    detected: bool = Field(..., description="Whether change was detected in this observation")
    cloud_cover: float = Field(0.0, description="Cloud cover percentage")
    is_independent: bool = Field(True, description="True if independent overpass, not second granule same-day")


class EvaluateLifecycleRequest(BaseModel):
    observations: list[ObservationItem] = Field(..., min_length=1)


class ClassifyHypothesisRequest(BaseModel):
    ndvi_delta: float = Field(0.0, description="Difference in NDVI (T2 - T1)")
    ndwi_delta: float = Field(0.0, description="Difference in NDWI (T2 - T1)")
    ndbi_delta: float = Field(0.0, description="Difference in NDBI (T2 - T1)")
    aspect_ratio: float = Field(1.0, ge=0.1, description="Bounding box length/width aspect ratio")


@router.get("")
async def get_timeline(
    aoi_id: str | None = Query(None, description="AOI UUID"),
    max_cloud_cover: float = Query(30.0, ge=0.0, le=100.0),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Retrieve all chronological acquisition nodes for an AOI."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())
    nodes = await fetch_aoi_timeline(session=db, aoi_id=aoi_id, max_cloud_cover=max_cloud_cover)
    return JSONResponse(
        content={
            "aoi_id": aoi_id,
            "nodes": [n.to_dict() for n in nodes],
            "count": len(nodes),
            "request_id": request_id,
        }
    )


@router.post("/evaluate")
async def evaluate_lifecycle(
    req: EvaluateLifecycleRequest,
    request: Request = None,
) -> JSONResponse:
    """
    Evaluate candidate change observations across a multi-temporal timeline.
    Enforces canonical ADR-007 rules: candidate vs confirmed vs inconsistent.
    """
    from datetime import datetime
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())

    formatted_obs = []
    for item in req.observations:
        dt = datetime.fromisoformat(item.timestamp.replace("Z", "+00:00"))
        formatted_obs.append({
            "timestamp": dt,
            "detected": item.detected,
            "cloud_cover": item.cloud_cover,
            "is_independent": item.is_independent,
        })

    result = evaluate_temporal_lifecycle(formatted_obs)
    return JSONResponse(content={**result, "request_id": request_id})


@router.post("/classify-hypothesis")
async def classify_hypothesis(
    req: ClassifyHypothesisRequest,
    request: Request = None,
) -> JSONResponse:
    """
    Propose spectral and morphological category hypotheses (Phase 8).
    Rules: NDVI decrease -> vegetation clearance; NDBI increase -> construction; elongated -> road.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())
    hypothesis = classify_change_hypothesis(
        ndvi_delta=req.ndvi_delta,
        ndwi_delta=req.ndwi_delta,
        ndbi_delta=req.ndbi_delta,
        aspect_ratio=req.aspect_ratio,
    )
    return JSONResponse(content={**hypothesis, "request_id": request_id})
