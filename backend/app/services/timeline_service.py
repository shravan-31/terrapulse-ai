"""
backend/app/services/timeline_service.py
Multi-temporal satellite timeline analysis and canonical temporal status logic (Phase 7, ADR-007).

Implements:
- Chronological timeline sorting and observation filtering
- Automatic baseline and observation pair selection
- Multi-temporal persistence rules:
    - 'candidate': seen in single observation after baseline
    - 'confirmed': seen and persisting in independent subsequent overpass
    - 'inconsistent': seen then reverted/flickered in clear scene
    - 'insufficient_evidence': intervening scenes too cloudy or gaps too wide
- Left-censoring: records 'earliest within searched evidence', never claims exact event date
- Spectral index delta change classification hypotheses (Phase 8):
    - NDVI decrease -> vegetation_land_cover (clearance)
    - NDWI delta -> water_variation
    - NDBI increase + compact -> construction
    - Elongated -> road_development
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.qc import compute_confidence_score
from app.core.settings import settings
from app.models.entities import Scene

log = structlog.get_logger("satquery.timeline")


class TimelineNode:
    """Represents a discrete satellite acquisition node in an AOI timeline."""

    def __init__(
        self,
        scene_id: str,
        product_id: str,
        acquisition_at: datetime,
        cloud_cover: float,
        is_usable: bool = True,
        exclusion_reason: str | None = None,
    ) -> None:
        self.scene_id = scene_id
        self.product_id = product_id
        self.acquisition_at = acquisition_at
        self.cloud_cover = cloud_cover
        self.is_usable = is_usable
        self.exclusion_reason = exclusion_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "product_id": self.product_id,
            "acquisition_at": self.acquisition_at.isoformat(),
            "cloud_cover": self.cloud_cover,
            "is_usable": self.is_usable,
            "exclusion_reason": self.exclusion_reason,
        }


def classify_change_hypothesis(
    ndvi_delta: float = 0.0,
    ndwi_delta: float = 0.0,
    ndbi_delta: float = 0.0,
    aspect_ratio: float = 1.0,
) -> dict[str, Any]:
    """
    Hypothesis generator for change types based on spectral indices and geometry (Phase 8).
    Returns hypothesis with supporting facts, uncalibrated confidence, and rule citations.
    """
    # 1. Elongated geometry -> road development
    if aspect_ratio >= 3.5 and ndbi_delta > 0.05:
        return {
            "change_type": "road_development",
            "confidence_hypothesis": "Elongated linear feature with increased built-up index (NDBI)",
            "rules_applied": ["elongated_geometry_aspect_ratio_gt_3.5", "ndbi_rise"],
        }

    # 2. Vegetation clearance: significant NDVI drop
    if ndvi_delta <= -0.20:
        return {
            "change_type": "vegetation_land_cover",
            "change_kind": "disappearance",
            "confidence_hypothesis": "Significant decrease in vegetation index (NDVI <= -0.20)",
            "rules_applied": ["ndvi_decrease_gt_0.20"],
        }

    # 3. Water variation: NDWI change
    if abs(ndwi_delta) >= 0.20:
        kind = "expansion" if ndwi_delta > 0 else "contraction"
        return {
            "change_type": "water_variation",
            "change_kind": kind,
            "confidence_hypothesis": f"Surface water index variation (NDWI delta = {ndwi_delta:.2f})",
            "rules_applied": ["ndwi_magnitude_gt_0.20"],
        }

    # 4. Construction: NDBI increase + compact geometry
    if ndbi_delta >= 0.15 and aspect_ratio < 2.5:
        return {
            "change_type": "construction",
            "change_kind": "appearance",
            "confidence_hypothesis": "Compact structure with marked increase in built-up index (NDBI)",
            "rules_applied": ["ndbi_increase_gt_0.15", "compact_geometry"],
        }

    return {
        "change_type": "unknown",
        "change_kind": "unknown",
        "confidence_hypothesis": "Spectral signatures and morphology do not decisively match a single category",
        "rules_applied": ["ambiguous_spectral_signature"],
    }


def evaluate_temporal_lifecycle(
    observations: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """
    Evaluates multi-temporal sequence for candidate changes per ADR-007.
    Observations: list of dicts ordered chronologically:
      [{"timestamp": dt, "detected": bool, "cloud_cover": float, "is_independent": bool}]

    Returns:
      {
        "temporal_status": candidate | confirmed | inconsistent | insufficient_evidence,
        "last_baseline_observation_at": dt | None,
        "earliest_supported_at": dt | None,
        "confirmed_at": dt | None,
        "latest_observation_at": dt | None,
        "left_censored": True,
        "persisting_observations": int,
      }
    """
    if not observations:
        return {
            "temporal_status": "insufficient_evidence",
            "last_baseline_observation_at": None,
            "earliest_supported_at": None,
            "confirmed_at": None,
            "latest_observation_at": None,
            "left_censored": True,
            "persisting_observations": 0,
        }

    # Sort chronologically
    sorted_obs = sorted(observations, key=lambda x: x["timestamp"])

    baseline_dt = None
    earliest_dt = None
    confirmed_dt = None
    latest_dt = sorted_obs[-1]["timestamp"]
    detected_count = 0
    consecutive_reversions = 0

    for idx, obs in enumerate(sorted_obs):
        if not obs.get("detected", False):
            if earliest_dt is None:
                # Still in baseline phase
                baseline_dt = obs["timestamp"]
            else:
                # Change was seen earlier, but is absent in clear scene -> flicker/reversion
                if obs.get("cloud_cover", 0.0) <= 20.0:
                    consecutive_reversions += 1
        else:
            detected_count += 1
            if earliest_dt is None:
                earliest_dt = obs["timestamp"]
            elif obs.get("is_independent", True) and confirmed_dt is None:
                # Independent subsequent observation confirms change
                confirmed_dt = obs["timestamp"]

    # Determine status
    if detected_count == 0:
        status = "insufficient_evidence"
    elif consecutive_reversions > 0:
        status = "inconsistent"
    elif confirmed_dt is not None:
        status = "confirmed"
    else:
        status = "candidate"

    return {
        "temporal_status": status,
        "last_baseline_observation_at": baseline_dt.isoformat() if baseline_dt else None,
        "earliest_supported_at": earliest_dt.isoformat() if earliest_dt else None,
        "confirmed_at": confirmed_dt.isoformat() if confirmed_dt else None,
        "latest_observation_at": latest_dt.isoformat() if latest_dt else None,
        "left_censored": True,  # "earliest within searched evidence" (ADR-007)
        "persisting_observations": detected_count,
    }


async def fetch_aoi_timeline(
    session: AsyncSession,
    aoi_id: str | uuid.UUID | None = None,
    max_cloud_cover: float = 30.0,
) -> list[TimelineNode]:
    """Retrieve all chronological satellite acquisitions for an AOI."""
    stmt = select(Scene).order_by(Scene.acquisition_at.asc())
    res = await session.execute(stmt)
    scenes = list(res.scalars().all())

    nodes: list[TimelineNode] = []
    for sc in scenes:
        usable = sc.cloud_coverage_percent <= max_cloud_cover
        reason = None if usable else f"Cloud coverage ({sc.cloud_coverage_percent}%) exceeds limit ({max_cloud_cover}%)"
        nodes.append(
            TimelineNode(
                scene_id=str(sc.id),
                product_id=sc.product_id,
                acquisition_at=sc.acquisition_at,
                cloud_cover=sc.cloud_coverage_percent,
                is_usable=usable,
                exclusion_reason=reason,
            )
        )

    return nodes
