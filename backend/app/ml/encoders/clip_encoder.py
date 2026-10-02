"""
backend/app/ml/encoders/clip_encoder.py
Standard CLIP encoder and deterministic test encoder.
Provides reliable offline execution and fallback.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image
import structlog

from app.ml.encoders.base_encoder import BaseEncoder, normalize_l2

log = structlog.get_logger("satquery.ml.clip")


class DeterministicOfflineEncoder(BaseEncoder):
    """
    Deterministic pseudo-embedding model for offline testing and development.
    Generates repeatable 768-dimensional float32 L2-normalized vectors
    without requiring heavy PyTorch weights downloads.
    Strictly follows ADR-014: labeled explicitly as offline deterministic simulator.
    """

    def __init__(self, dimension: int = 768) -> None:
        self._dimension = dimension
        self._model_name = "Deterministic-Offline-Encoder"
        self._hash = "offline_sim_768_deterministic"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def checkpoint_hash(self) -> str | None:
        return self._hash

    @property
    def is_available(self) -> bool:
        return True

    def embed_text(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        vectors = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            seed = int(hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            vectors[i] = rng.randn(self._dimension).astype(np.float32)

        return normalize_l2(vectors)

    def embed_images(self, images: Sequence[np.ndarray | Image.Image | str | Path]) -> np.ndarray:
        if not images:
            return np.empty((0, self._dimension), dtype=np.float32)

        vectors = np.zeros((len(images), self._dimension), dtype=np.float32)
        for i, item in enumerate(images):
            if isinstance(item, np.ndarray):
                digest = hashlib.sha256(item.tobytes()[:2048]).hexdigest()
            elif isinstance(item, (str, Path)):
                digest = hashlib.sha256(str(item).encode()).hexdigest()
            else:
                digest = hashlib.sha256(item.tobytes()[:2048]).hexdigest()
            seed = int(digest[:8], 16)
            rng = np.random.RandomState(seed)
            vectors[i] = rng.randn(self._dimension).astype(np.float32)

        return normalize_l2(vectors)
