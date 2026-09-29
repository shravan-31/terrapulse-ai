"""
backend/app/schemas/entities.py
Pydantic schemas for SatQuery AI API request/response validation.

Enforces:
1. Canonical field definitions (ADR-007):
   - change_type, change_kind, temporal_status, review_status
2. Quality score & factors schema (ADR-013)
3. Job progress & SSE event schemas (ADR-005)
4. Provenance audit logs (ADR-002, ADR-015)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# AOI Schemas
# ---------------------------------------------------------------------------
class AOIBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    geometry: dict[str, Any] = Field(..., description="GeoJSON Polygon geometry")


class AOICreate(AOIBase):
    pass


class AOIResponse(AOIBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    area_km2: float
    vertex_count: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Scene Schemas
# ---------------------------------------------------------------------------
class SceneAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_type: str
    local_path: str
    checksum_sha256: str
    resolution_m: float


class SceneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    product_id: str
    acquisition_at: datetime
    cloud_coverage_percent: float
    footprint: dict[str, Any]
    crs: str
    metadata_json: dict[str, Any]
    created_at: datetime


# ---------------------------------------------------------------------------
# Change & Decision Schemas (ADR-007, ADR-013)
# ---------------------------------------------------------------------------
ChangeType = Literal[
    "construction",
    "clearance",
    "water_variation",
    "vegetation_land_cover",
    "road_development",
    "unknown",
]

ChangeKind = Literal[
    "appearance",
    "disappearance",
    "expansion",
    "contraction",
    "unknown",
]

TemporalStatus = Literal[
    "candidate",
    "confirmed",
    "inconsistent",
    "insufficient_evidence",
]

ReviewStatus = Literal[
    "pending",
    "confirmed_by_analyst",
    "rejected_by_analyst",
    "flagged",
]


class AnalystDecisionCreate(BaseModel):
    review_status: ReviewStatus
    notes: str | None = None


class AnalystDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    change_id: uuid.UUID
    operator: str
    review_status: ReviewStatus
    notes: str | None
    created_at: datetime


class ChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_id: uuid.UUID
    change_type: ChangeType
    change_kind: ChangeKind
    temporal_status: TemporalStatus
    last_baseline_observation_at: datetime | None
    earliest_supported_at: datetime
    confirmed_at: datetime | None
    latest_observation_at: datetime
    polygon: dict[str, Any]
    area_m2: float
    pixel_count: int
    confidence_score: float
    confidence_details: dict[str, Any]
    created_at: datetime


# ---------------------------------------------------------------------------
# Job & Event Schemas (ADR-005)
# ---------------------------------------------------------------------------
class JobEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    event_type: str
    message: str
    event_data: dict[str, Any]
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: Literal["pending", "running", "completed", "failed"]
    progress_percent: float
    error_message: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Provenance Schemas (ADR-002, ADR-015)
# ---------------------------------------------------------------------------
class ProvenanceCreate(BaseModel):
    artifact_id: str
    artifact_type: str
    parent_artifact_ids: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    model_name: str | None = None
    model_sha256: str | None = None
    code_version: str = "0.1.0"
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProvenanceResponse(ProvenanceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Ingestion Schemas (Phase 3)
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    aoi_id: str = Field(..., description="UUID or identifier of the target AOI")
    start_date: datetime = Field(..., description="Start of search interval (ISO format)")
    end_date: datetime = Field(..., description="End of search interval (ISO format)")
    max_cloud_cover: float = Field(default=30.0, ge=0.0, le=100.0, description="Maximum allowed cloud coverage percentage")
    max_scenes: int = Field(default=5, ge=1, le=50, description="Max scenes to discover and ingest")
    idempotency_key: str | None = Field(default=None, description="Optional client idempotency key")


class IngestResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    message: str
    request_id: str

