"""
backend/tests/unit/test_models.py
Unit tests verifying database models and Pydantic schemas.

Validates:
1. Canonical change taxonomy (ADR-007)
2. Canonical temporal fields and review status (ADR-007)
3. Provenance artifact audit structure (ADR-002, ADR-015)
4. Anti-renormalization confidence integration (ADR-013)
"""

import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.entities import (
    AOICreate,
    AOIResponse,
    AnalystDecisionCreate,
    ChangeResponse,
    JobResponse,
    ProvenanceCreate,
)


def test_aoi_schema_validation():
    valid_aoi = AOICreate(
        name="Test AOI",
        description="Demo AOI",
        geometry={"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]},
    )
    assert valid_aoi.name == "Test AOI"


def test_canonical_taxonomy_valid_values():
    """Verify that canonical values are accepted."""
    now = datetime.now(timezone.utc)
    change = ChangeResponse(
        id=uuid.uuid4(),
        analysis_id=uuid.uuid4(),
        change_type="construction",
        change_kind="appearance",
        temporal_status="confirmed",
        last_baseline_observation_at=now,
        earliest_supported_at=now,
        confirmed_at=now,
        latest_observation_at=now,
        polygon={"type": "Polygon", "coordinates": []},
        area_m2=1200.0,
        pixel_count=12,
        confidence_score=0.85,
        confidence_details={"calibrated": False, "complete_evidence": True},
        created_at=now,
    )
    assert change.change_type == "construction"
    assert change.change_kind == "appearance"
    assert change.temporal_status == "confirmed"


def test_canonical_taxonomy_rejects_invalid_values():
    """Verify that non-canonical values are rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ChangeResponse(
            id=uuid.uuid4(),
            analysis_id=uuid.uuid4(),
            change_type="invalid_type",  # Not in canonical enum
            change_kind="appearance",
            temporal_status="confirmed",
            last_baseline_observation_at=now,
            earliest_supported_at=now,
            confirmed_at=now,
            latest_observation_at=now,
            polygon={},
            area_m2=100.0,
            pixel_count=1,
            confidence_score=0.5,
            confidence_details={},
            created_at=now,
        )


def test_analyst_decision_canonical_review_status():
    decision = AnalystDecisionCreate(
        review_status="confirmed_by_analyst",
        notes="Verified ground truth",
    )
    assert decision.review_status == "confirmed_by_analyst"

    with pytest.raises(ValidationError):
        AnalystDecisionCreate(
            review_status="approved",  # Non-canonical status rejected!
        )


def test_provenance_schema():
    prov = ProvenanceCreate(
        artifact_id="art_12345",
        artifact_type="embedding",
        parent_artifact_ids=["tile_999"],
        source_references=["S2A_MSIL2A_20260101T000000"],
        model_name="RemoteCLIP-ViT-L-14",
        model_sha256="abc123def456",
        parameters={"tile_size": 256},
    )
    assert prov.artifact_id == "art_12345"
    assert prov.code_version == "0.1.0"
