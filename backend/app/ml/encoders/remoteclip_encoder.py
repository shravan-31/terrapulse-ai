"""
backend/app/ml/encoders/remoteclip_encoder.py
RemoteCLIP vision-language encoder for satellite imagery.
Uses official RemoteCLIP-ViT-L-14 weights trained on remote sensing data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image
import structlog

from app.ml.encoders.base_encoder import BaseEncoder, normalize_l2

log = structlog.get_logger("satquery.ml.remoteclip")


class RemoteCLIPEncoder(BaseEncoder):
    """
    Adapter for official RemoteCLIP-ViT-L-14 pretrained weights.
    Loads PyTorch model into eval mode with bounded batching and L2 normalization.
    """

    def __init__(
        self,
        model_path: str | Path = "./models/remoteclip/RemoteCLIP-ViT-L-14.pt",
        device: str = "cpu",
        batch_size: int = 8,
    ) -> None:
        self._model_path = Path(model_path)
        self._batch_size = max(1, batch_size)
        self._model_name = "RemoteCLIP-ViT-L-14"
        self._dimension = 768
        self._device_str = device
        self._model: Any = None
        self._preprocess: Any = None
        self._tokenizer: Any = None
        self._actual_sha256: str | None = None
        self._target_device: str = "cpu"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def checkpoint_hash(self) -> str | None:
        return self._actual_sha256

    @property
    def is_available(self) -> bool:
        if not self._model_path.exists():
            return False
        try:
            import torch
            import open_clip
            return True
        except ImportError:
            return False

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"RemoteCLIP checkpoint not found at '{self._model_path}'. "
                "Run setup scripts or ensure file exists."
            )

        hasher = hashlib.sha256()
        with open(self._model_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        self._actual_sha256 = hasher.hexdigest()

        import torch
        import open_clip

        target_device = "cuda" if (self._device_str.lower() == "cuda" and torch.cuda.is_available()) else "cpu"
        log.info("Loading RemoteCLIP into memory", device=target_device, path=str(self._model_path))

        model, _, preprocess = open_clip.create_model_and_transforms("ViT-L-14")
        checkpoint = torch.load(str(self._model_path), map_location="cpu")
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            checkpoint = checkpoint["state_dict"]
        model.load_state_dict(checkpoint)
        model.to(target_device)
        model.eval()

        self._model = model
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer("ViT-L-14")
        self._target_device = target_device
        log.info("RemoteCLIP loaded successfully", model=self._model_name, device=target_device)

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
