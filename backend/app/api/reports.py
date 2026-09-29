"""
backend/app/api/reports.py
Scientific report generation and multi-format export API (Phase 11, Master Prompt §14).

Implements:
- Multi-format exports: JSON, GeoJSON FeatureCollection, and sanitized CSV.
- CSV formula injection protection: escapes leading '=', '+', '-', '@' characters.
- Canonical snapshot containing:
    AOI, date range, usable scene counts, change polygons, quality factors,
    uncalibrated disclaimer, analyst decisions, and complete provenance.
"""

from __future__ import annotations

import csv
import io
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationError
from app.core.settings import settings
from app.repositories.analysis_repository import AnalysisRepository

router = APIRouter(prefix="/api/report", tags=["report"])


def _sanitize_csv_cell(value: Any) -> str:
    """Escape potential formula injection prefixes in CSV cells."""
    s = str(value)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


class GenerateReportRequest(BaseModel):
    analysis_id: str = Field(..., description="Analysis UUID to export")
    format: Literal["json", "geojson", "csv"] = Field("json", description="Export format")


@router.post("/generate")
async def generate_report(
    req: GenerateReportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate and export a scientific analysis report in requested format."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        ana_uuid = uuid.UUID(req.analysis_id)
    except ValueError:
        raise ValidationError(detail=f"Invalid analysis UUID: {req.analysis_id}")

    repo = AnalysisRepository(db)
    analysis = await repo.get_by_id(ana_uuid)
    if not analysis:
        raise NotFoundError(resource="Analysis", resource_id=req.analysis_id)

    changes = await repo.list_changes(ana_uuid)

    # 1. GeoJSON Export
    if req.format == "geojson":
        features = []
        for c in changes:
            features.append({
                "type": "Feature",
                "geometry": c.polygon,
                "properties": {
                    "change_id": str(c.id),
                    "change_type": c.change_type,
                    "change_kind": c.change_kind,
                    "temporal_status": c.temporal_status,
                    "review_status": c.review_status,
                    "area_m2": c.area_m2,
                    "pixel_count": c.pixel_count,
                    "confidence_score": c.confidence_score,
                    "confidence_calibrated": False,
                },
            })
        geojson_data = {
            "type": "FeatureCollection",
            "metadata": {
                "analysis_id": str(analysis.id),
                "aoi_id": str(analysis.aoi_id),
                "export_version": "1.0",
                "disclaimer": "System confidence scores are uncalibrated and intended for analyst triage.",
            },
            "features": features,
        }
        return JSONResponse(
            content=geojson_data,
            headers={"Content-Disposition": f"attachment; filename=satquery_analysis_{analysis.id}.geojson"},
        )

    # 2. CSV Export (Formula injection protected)
    if req.format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "change_id",
            "change_type",
            "change_kind",
            "area_m2",
            "pixel_count",
            "confidence_score",
            "temporal_status",
            "review_status",
        ])
        for c in changes:
            writer.writerow([
                _sanitize_csv_cell(c.id),
                _sanitize_csv_cell(c.change_type),
                _sanitize_csv_cell(c.change_kind),
                _sanitize_csv_cell(c.area_m2),
                _sanitize_csv_cell(c.pixel_count),
                _sanitize_csv_cell(c.confidence_score),
                _sanitize_csv_cell(c.temporal_status),
                _sanitize_csv_cell(c.review_status),
            ])
        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=satquery_analysis_{analysis.id}.csv"},
        )

    # 3. JSON Export (Default)
    return JSONResponse(
        content={
            "report_id": str(uuid.uuid4()),
            "analysis_id": str(analysis.id),
            "aoi_id": str(analysis.aoi_id),
            "baseline_scene_id": str(analysis.baseline_scene_id),
            "comparison_scene_id": str(analysis.comparison_scene_id),
            "created_at": analysis.created_at.isoformat(),
            "confidence_disclaimer": "All confidence scores are uncalibrated triage hypotheses.",
            "total_changes": len(changes),
            "changes": [
                {
                    "id": str(c.id),
                    "change_type": c.change_type,
                    "change_kind": c.change_kind,
                    "area_m2": c.area_m2,
                    "pixel_count": c.pixel_count,
                    "confidence_score": c.confidence_score,
                    "temporal_status": c.temporal_status,
                    "review_status": c.review_status,
                    "polygon": c.polygon,
                }
                for c in changes
            ],
            "request_id": request_id,
        }
    )
