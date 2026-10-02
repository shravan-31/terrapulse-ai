"""
backend/app/ml/change_detection/__init__.py
Change detector factory and registry.
"""

from __future__ import annotations

from typing import Literal, Optional
from app.ml.change_detection.base_detector import (
    BaseChangeDetector,
    ChangeComponent,
    ChangeDetectionResult,
)
from app.ml.change_detection.classical_detector import ClassicalSpectralChangeDetector
from app.ml.change_detection.deep_detector import DeepLearningChangeDetector

_classical_singleton: Optional[ClassicalSpectralChangeDetector] = None
_deep_singleton: Optional[DeepLearningChangeDetector] = None


def get_change_detector(method: Literal["classical", "deep"] = "classical") -> BaseChangeDetector:
    """Retrieve change detection model instance based on configured method."""
    global _classical_singleton, _deep_singleton

    if method == "deep":
        if _deep_singleton is None:
            _deep_singleton = DeepLearningChangeDetector()
        return _deep_singleton

    if _classical_singleton is None:
        _classical_singleton = ClassicalSpectralChangeDetector()
    return _classical_singleton
