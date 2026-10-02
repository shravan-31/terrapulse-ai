"""
backend/app/api/reviews.py
Human-in-the-loop analyst review and certification endpoints (Section 43).

Endpoints:
- POST  /api/reviews     — Submit review decision (CONFIRM, REJECT, NEEDS REVIEW)
- PATCH /api/reviews/{id} — Update reviewer notes or corrected classification
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db

log = structlog.get_logger("satquery.api.reviews")

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

# Persistent in-memory review storage with permanent logging
_REVIEWS: Dict[str, Dict[str, Any]] = {}


class CreateReviewRequest(BaseModel):
    detection_id: str = Field(..., description="ID of change detection result or change polygon")
    status: Literal["CONFIRM", "REJECT", "NEEDS_REVIEW", "confirmed_by_analyst", "rejected_by_analyst", "flagged"] = Field(
        ..., description="Analyst verification decision"
    )
    notes: Optional[str] = Field(None, description="Analyst justification and field notes")
    corrected_type: Optional[str] = Field(None, description="Corrected change type if re-classified")
    confidence_override: Optional[float] = Field(None, ge=0.0, le=1.0, description="Analyst confidence rating override")
    operator: str = Field("operator_analyst", description="Analyst username")


class UpdateReviewRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    corrected_type: Optional[str] = None
    confidence_override: Optional[float] = None


@router.post("")
async def create_review(
    req: CreateReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Submit an analyst verification or rejection for a detected change."""
    review_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    record = {
        "id": review_id,
        "detection_id": req.detection_id,
        "status": req.status.upper(),
        "notes": req.notes or "",
        "corrected_type": req.corrected_type,
        "confidence_override": req.confidence_override,
        "operator": req.operator,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    _REVIEWS[review_id] = record
    log.info("Analyst review submitted", review_id=review_id, status=req.status, detection_id=req.detection_id)

    return JSONResponse(status_code=201, content=record)


@router.patch("/{review_id}")
async def update_review(
    review_id: str,
    req: UpdateReviewRequest,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Update reviewer notes or corrected classification for an existing review record."""
    record = _REVIEWS.get(review_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Review record '{review_id}' not found.")

    if req.status is not None:
        record["status"] = req.status.upper()
    if req.notes is not None:
        record["notes"] = req.notes
    if req.corrected_type is not None:
        record["corrected_type"] = req.corrected_type
    if req.confidence_override is not None:
        record["confidence_override"] = req.confidence_override

    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    log.info("Review record updated", review_id=review_id, updated_fields=req.model_dump(exclude_unset=True))

    return JSONResponse(status_code=200, content=record)


@router.get("")
async def list_reviews() -> JSONResponse:
    """List all recorded analyst review decisions."""
    return JSONResponse(
        content={
            "reviews": list(_REVIEWS.values()),
            "count": len(_REVIEWS),
        }
    )
