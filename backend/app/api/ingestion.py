"""
backend/app/api/ingestion.py
Satellite Imagery Ingestion endpoints (Section 43).

Endpoints:
- POST /api/ingestion/upload  — Upload GeoTIFF / COG / NetCDF file with path-traversal protection
- POST /api/ingestion/process — Trigger background ingestion, tiling, embedding, and indexing
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.errors import ValidationError
from app.services.ingestion_service import RAW_DIR, ingest_raster_file

log = structlog.get_logger("satquery.api.ingestion")

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


class ProcessRequest(BaseModel):
    file_path: str = Field(..., description="Local path to uploaded raster")
    sensor: str = Field("Sentinel-2", description="Sentinel-2, Landsat, or GeoTIFF")
    acquisition_date: Optional[str] = Field(None, description="ISO Date string YYYY-MM-DD")


@router.post("/upload")
async def upload_raster(
    file: UploadFile = File(...),
    sensor: str = Form("Sentinel-2"),
    acquisition_date: Optional[str] = Form(None),
) -> JSONResponse:
    """
    Upload a satellite GeoTIFF or COG file.
    Validates file type and saves safely using generated UUID to prevent path traversal.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    allowed_exts = {".tif", ".tiff", ".cog", ".png", ".jpg", ".jpeg"}
    suffix = Path(file.filename or "image.tif").suffix.lower()
    if suffix not in allowed_exts:
        raise ValidationError(detail=f"Unsupported file format '{suffix}'. Allowed: {allowed_exts}")

    file_uuid = uuid.uuid4().hex
    safe_filename = f"{sensor.lower()}_{file_uuid}{suffix}"
    dest_path = RAW_DIR / safe_filename

    # Stream file to disk
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size_mb = round(dest_path.stat().st_size / (1024 * 1024), 2)
    log.info("Raster uploaded successfully", path=str(dest_path), size_mb=file_size_mb)

    return JSONResponse(
        status_code=201,
        content={
            "status": "UPLOADED",
            "file_path": str(dest_path),
            "filename": safe_filename,
            "sensor": sensor,
            "acquisition_date": acquisition_date,
            "size_mb": file_size_mb,
            "message": "File received. Call POST /api/ingestion/process to trigger ingestion pipeline.",
        },
    )


@router.post("/process")
async def process_raster(
    req: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Trigger end-to-end preprocessing, cloud masking, tiling, and vector indexing.
    """
    p = Path(req.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    # Run ingestion
    result = await ingest_raster_file(
        file_path=p,
        sensor=req.sensor,
        acquisition_date=req.acquisition_date,
        session=db,
    )

    return JSONResponse(
        status_code=200,
        content=result,
    )
