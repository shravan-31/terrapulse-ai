"""
backend/app/ml/encoders/base_encoder.py
Base abstraction for multimodal vision-language satellite encoders.

Specifies:
- Abstract BaseEncoder with dimension, model_name, checkpoint_hash, is_available
- embed_text: Sequence[str] -> np.ndarray (N, dim), L2-normalized float32
- embed_images: Sequence[image] -> np.ndarray (N, dim), L2-normalized float32
- Strict validation: checks finite values and L2 normalization
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Sequence
import numpy as np
from PIL import Image


def normalize_l2(vectors: np.ndarray) -> np.ndarray:
    """Normalize vectors to unit Euclidean length along the last dimension."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    normalized = (vectors / norms).astype(np.float32)
    if not np.all(np.isfinite(normalized)):
        raise ValueError("Non-finite values encountered in embedding normalization")
    return normalized


class BaseEncoder(abc.ABC):
    """Abstract base class for satellite image and text encoders."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension (e.g., 768)."""
        ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Canonical model name."""
        ...

    @property
    @abc.abstractmethod
    def checkpoint_hash(self) -> str | None:
        """SHA-256 hash of loaded checkpoint, if applicable."""
        ...

    @property
    @abc.abstractmethod
    def is_available(self) -> bool:
        """Whether model weights and dependencies are available on this system."""
        ...

    @abc.abstractmethod
    def embed_text(self, texts: Sequence[str]) -> np.ndarray:
        """
        Embed natural language queries.
        Returns:
            np.ndarray of shape (N, dimension) float32, L2-normalized.
        """
        ...

    @abc.abstractmethod
    def embed_images(self, images: Sequence[np.ndarray | Image.Image | str | Path]) -> np.ndarray:
        """
        Embed satellite imagery tiles or rasters.
        Returns:
            np.ndarray of shape (N, dimension) float32, L2-normalized.
        """
        ...
