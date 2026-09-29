"""
backend/tests/unit/test_confidence.py
Tests for ADR-013: Anti-renormalization policy for quality confidence scoring.

Proves:
1. Missing quality evidence cannot increase confidence through weight renormalization.
2. A high model score alone cannot produce high confidence when quality factors are absent.
3. Adding real quality evidence increases confidence monotonically; missing factors act as a strict ceiling.
4. Output schema strictly adheres to ADR-013 with calibrated: False.
"""

import pytest
from app.core.qc import compute_confidence_score, DEFAULT_CONFIDENCE_WEIGHTS


def test_missing_factors_cannot_increase_confidence_via_renormalization():
    """
    If weight renormalization were permitted:
      Only model_score=0.95 available (weight=0.10).
      Renormalized score = 0.95 / 0.10 * 0.10 = 0.95 (dangerously high!).
    
    Under ADR-013 (Anti-Renormalization):
      Score = 0.10 * 0.95 = 0.095.
      Missing quality evidence strictly caps confidence and cannot artificially inflate it.
    """
    partial_factors = {
        "model_score": 0.95,
        # valid_ratio, registration_quality, cloud_quality, season_similarity, temporal_consistency MISSING
    }
    
    result = compute_confidence_score(partial_factors)
    
    # Prove score is not renormalized to ~0.95
    assert result.score <= 0.10, f"Expected score <= 0.10, got {result.score}"
    assert result.score == 0.095
    assert not result.complete_evidence
    assert "registration_quality" in result.missing_factors
    assert "cloud_quality" in result.missing_factors
    assert result.calibrated is False


def test_comparing_renormalization_vs_adr013():
    """
    Direct proof: calculates what a naive renormalized algorithm would output
    vs the ADR-013 policy, confirming ADR-013 prevents confidence inflation.
    """
    factor_values = {
        "model_score": 0.90,
        "valid_ratio": 0.80,
        # registration, cloud, season, temporal are missing
    }
    
    # Naive weight renormalization calculation:
    available_weights = DEFAULT_CONFIDENCE_WEIGHTS["model_score"] + DEFAULT_CONFIDENCE_WEIGHTS["valid_ratio"]  # 0.10 + 0.20 = 0.30
    renormalized_score = (0.10 * 0.90 + 0.20 * 0.80) / available_weights  # (0.09 + 0.16) / 0.30 = 0.8333
    
    # ADR-013 calculation:
    result = compute_confidence_score(factor_values)
    
    # Prove ADR-013 score is strictly less than renormalized score when factors are missing
    assert result.score < renormalized_score
    assert result.score == 0.25  # exactly 0.09 + 0.16, capped by 0.30 max possible


def test_full_evidence_scores_higher_than_missing_evidence():
    """
    Providing verified quality evidence strictly yields higher confidence
    than when that evidence is missing.
    """
    partial_evidence = {
        "model_score": 0.90,
    }
    
    complete_evidence = {
        "model_score": 0.90,
        "valid_ratio": 0.95,
        "registration_quality": 0.90,
        "cloud_quality": 0.85,
        "season_similarity": 0.90,
        "temporal_consistency": 0.95,
    }
    
    partial_result = compute_confidence_score(partial_evidence)
    complete_result = compute_confidence_score(complete_evidence)
    
    assert complete_result.score > partial_result.score
    assert complete_result.complete_evidence is True
    assert len(complete_result.missing_factors) == 0
    assert complete_result.score > 0.85
