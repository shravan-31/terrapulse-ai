"""
backend/app/ml/encoders/openclip_encoder.py
OpenCLIP general encoder adapter.
Supports local checkpoints or pre-cached open_clip model weights.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image
import structlog

from app.ml.encoders.base_encoder import BaseEncoder, normalize_l2

log = structlog.get_logger("satquery.ml.openclip")


class OpenCLIPEncoder(BaseEncoder):
    """
    Adapter for standard OpenCLIP models (e.g., ViT-B-32, ViT-L-14).
    """

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str = "cpu",
        batch_size: int = 8,
    ) -> None:
        self._arch_name = model_name
        self._pretrained = pretrained
        self._batch_size = max(1, batch_size)
        self._model_name = f"OpenCLIP-{model_name}"
        self._dimension = 512 if "B-32" in model_name or "B-16" in model_name else 768
        self._device_str = device
        self._model: Any = None
        self._preprocess: Any = None
        self._tokenizer: Any = None
        self._target_device: str = "cpu"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def checkpoint_hash(self) -> str | None:
        return f"openclip_{self._arch_name}_{self._pretrained}"

    @property
    def is_available(self) -> bool:
        try:
            import open_clip
            import torch
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        import torch
        import open_clip

        target_device = "cuda" if (self._device_str.lower() == "cuda" and torch.cuda.is_available()) else "cpu"
        log.info("Loading OpenCLIP model", model=self._arch_name, pretrained=self._pretrained, device=target_device)

        model, _, preprocess = open_clip.create_model_and_transforms(
            self._arch_name,
            pretrained=self._pretrained,
            device=target_device,
        )
        model.eval()

        self._model = model
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(self._arch_name)
        self._target_device = target_device
        self._dimension = getattr(model, "visual", None) and getattr(model.visual, "output_dim", self._dimension)

    def embed_text(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        self._ensure_loaded()
        import torch

        all_embeddings: list[np.ndarray] = []
        batch_size = self._batch_size

        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            tokens = self._tokenizer(batch).to(self._target_device)
            with torch.no_grad():
                features = self._model.encode_text(tokens)
            all_embeddings.append(features.cpu().numpy())

        combined = np.vstack(all_embeddings)
        return normalize_l2(combined)

    def embed_images(self, images: Sequence[np.ndarray | Image.Image | str | Path]) -> np.ndarray:
        if not images:
            return np.empty((0, self._dimension), dtype=np.float32)

        self._ensure_loaded()
        import torch

        all_embeddings: list[np.ndarray] = []
        batch_size = self._batch_size

        for i in range(0, len(images), batch_size):
            batch_items = images[i : i + batch_size]
            tensors = []
            for item in batch_items:
                if isinstance(item, (str, Path)):
                    pil_img = Image.open(item).convert("RGB")
                elif isinstance(item, np.ndarray):
                    pil_img = Image.fromarray(item).convert("RGB")
                else:
                    pil_img = item.convert("RGB")
                tensors.append(self._preprocess(pil_img))

            batch_tensor = torch.stack(tensors).to(self._target_device)
            with torch.no_grad():
                features = self._model.encode_image(batch_tensor)

            all_embeddings.append(features.cpu().numpy())

        combined = np.vstack(all_embeddings)
        return normalize_l2(combined)
