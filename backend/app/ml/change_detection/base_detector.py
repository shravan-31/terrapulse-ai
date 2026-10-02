"""
backend/app/ml/change_detection/base_detector.py
Abstract base class and data structures for bi-temporal satellite change detection.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, List
import numpy as np


@dataclass
class ChangeComponent:
    """Represents an individual connected changed region."""
    polygon: dict[str, Any]  # GeoJSON Polygon geometry
    bbox_pixel: list[int]    # [r0, c0, r1, c1]
    pixel_count: int
    area_m2: float
    confidence: float
    change_type: str         # construction, vegetation loss, vegetation growth, water change, road development, urban expansion, land-use change, unknown
    spectral_delta: dict[str, float] = field(default_factory=dict)


@dataclass
class ChangeDetectionResult:
    """Full outcome of a bi-temporal change analysis run."""
    before_image: np.ndarray       # RGB array (H, W, 3)
    after_image: np.ndarray        # RGB array (H, W, 3)
    change_mask: np.ndarray         # Boolean array (H, W)
    change_overlay: np.ndarray      # RGBA array (H, W, 4) with highlighted changes
    components: List[ChangeComponent]
    total_change_area_m2: float
    total_aoi_area_m2: float
    percentage_change: float
    primary_change_type: str
    overall_confidence: float
    methodology: str
    parameters: dict[str, Any]


class BaseChangeDetector(abc.ABC):
    """Abstract interface for satellite change detection algorithms."""

    @property
    @abc.abstractmethod
    def algorithm_name(self) -> str:
        """Name of the algorithm/model."""
        ...

    @abc.abstractmethod
    def detect_changes(
        self,
        t1_image: np.ndarray,
        t2_image: np.ndarray,
        pixel_resolution_m: float = 10.0,
        threshold: float = 0.55,
        min_area_m2: float = 900.0,
        geotransform: tuple | None = None,
        crs_epsg: int = 4326,
    ) -> ChangeDetectionResult:
        """
        Detect changes between baseline (t1) and comparison (t2) imagery.
        """
        ...
