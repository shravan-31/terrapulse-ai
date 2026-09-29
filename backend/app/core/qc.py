"""
backend/app/core/qc.py
Quality Control and Confidence Scoring Engine for SatQuery AI.
Implements ADR-013: Anti-renormalization missing-factor policy.

Key invariants:
1. Base weights sum to <= 1.0.
2. Dynamic weight renormalization over available factors is strictly PROHIBITED.
3. Missing factors contribute 0.0 to the score numerator and their weight remains unallocated.
4. As a mathematical consequence, missing quality factors strictly cap the maximum possible
   confidence at sum(w_available), ensuring missing evidence CANNOT increase confidence.
5. All confidence scores explicitly report `calibrated: false`.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


DEFAULT_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "valid_ratio": 0.20,
    "registration_quality": 0.20,
    "cloud_quality": 0.15,
    "season_similarity": 0.15,
    "temporal_consistency": 0.20,
    "model_score": 0.10,
}


class FactorDetail(BaseModel):
    name: str
    value: float | None = None
    weight: float
    available: bool


class ConfidenceResult(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    calibrated: bool = False
    complete_evidence: bool
    weights_version: str
    factors: list[FactorDetail]
    missing_factors: list[str]
    rejection_reasons: list[str] = Field(default_factory=list)

    def __float__(self) -> float:
        return float(self.score)


def compute_confidence_score(
    factor_values: dict[str, float | None] | None = None,
    weights: dict[str, float] | None = None,
    weights_version: str = "v1.0",
    **kwargs: Any,
) -> ConfidenceResult:
    """
    Computes confidence score adhering to ADR-013 Anti-Renormalization Policy.
    Accepts factor_values dict or direct keyword arguments.
    """
    factors_map = dict(factor_values or {})
    for k, v in kwargs.items():
        if k in ("model_confidence", "model_score"):
            factors_map["model_score"] = float(v) if v is not None else None
        elif k in ("scl_valid_ratio", "valid_ratio"):
            factors_map["valid_ratio"] = float(v) if v is not None else None
        elif k in ("coregistration_error_px", "registration_quality"):
            if isinstance(v, (int, float)):
                factors_map["registration_quality"] = max(0.0, min(1.0, 1.0 - (float(v) / 2.0)))
            else:
                factors_map["registration_quality"] = None
        elif k in ("temporal_consistency_score", "temporal_consistency"):
            factors_map["temporal_consistency"] = float(v) if v is not None else None
        elif k in ("spatial_consistency_score", "cloud_quality"):
            factors_map["cloud_quality"] = float(v) if v is not None else None
        else:
            factors_map[k] = float(v) if isinstance(v, (int, float)) else None

    if weights is None:
        weights = DEFAULT_CONFIDENCE_WEIGHTS

    total_score = 0.0
    factors: list[FactorDetail] = []
    missing_factors: list[str] = []
    rejection_reasons: list[str] = []

    for name, weight in weights.items():
        val = factors_map.get(name)
        if val is not None and 0.0 <= val <= 1.0:
            factors.append(FactorDetail(name=name, value=val, weight=weight, available=True))
            total_score += weight * val
        else:
            factors.append(FactorDetail(name=name, value=None, weight=weight, available=False))
            missing_factors.append(name)

    # Ensure score stays bounded [0.0, 1.0]
    final_score = round(max(0.0, min(1.0, total_score)), 4)
    complete_evidence = len(missing_factors) == 0

    if not complete_evidence:
        rejection_reasons.append(
            f"Missing quality evidence for: {', '.join(missing_factors)}"
        )

    return ConfidenceResult(
        score=final_score,
        calibrated=False,
        complete_evidence=complete_evidence,
        weights_version=weights_version,
        factors=factors,
        missing_factors=missing_factors,
        rejection_reasons=rejection_reasons,
    )
