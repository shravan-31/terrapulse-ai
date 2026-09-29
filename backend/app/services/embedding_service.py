"""
backend/app/services/embedding_service.py
RemoteCLIP vision-language embedding service for satellite tiles and natural language queries.

Implements:
- EmbeddingModel interface (ADR-003, Master Prompt §8)
- RemoteCLIP adapter using open_clip ViT-L-14 weights
- Bounded batching, GPU/CPU device placement, GPU OOM recovery
- Strict L2-normalization to finite float32 vectors
- Model provenance and checkpoint hash tracking
- Deterministic mock adapter for unit tests and low-resource environments
"""

from __future__ import annotations

import abc
import hashlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import structlog
from PIL import Image

from app.core.errors import ModelMissingError
from app.core.settings import settings

log = structlog.get_logger("satquery.embedding")


class EmbeddingModel(abc.ABC):
    """Abstract base class for vision-language feature extractors."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Canonical model name."""
        ...

    @property
    @abc.abstractmethod
    def checkpoint_hash(self) -> str | None:
        """SHA-256 hash of loaded checkpoint."""
        ...

    @abc.abstractmethod
    def embed_text(self, texts: Sequence[str]) -> np.ndarray:
        """
        Embed a sequence of natural language prompts.
        Returns:
            np.ndarray of shape (N, dimension) with dtype float32, L2-normalized.
        """
        ...

    @abc.abstractmethod
    def embed_images(self, images: Sequence[np.ndarray | Image.Image | str | Path]) -> np.ndarray:
        """
        Embed a sequence of images (RGB arrays, PIL Images, or local filepaths).
        Returns:
            np.ndarray of shape (N, dimension) with dtype float32, L2-normalized.
        """
        ...


def _normalize_l2(vectors: np.ndarray) -> np.ndarray:
    """Normalize vectors to unit Euclidean length along the last dimension."""
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    normalized = (vectors / norms).astype(np.float32)
    if not np.all(np.isfinite(normalized)):
        raise ValueError("Non-finite values encountered in embedding normalization")
    return normalized


class RemoteCLIPAdapter(EmbeddingModel):
    """
    Adapter for official RemoteCLIP-ViT-L-14 pretrained weights.
    Loads PyTorch model into eval mode with bounded batching and L2 normalization.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        expected_sha256: str | None = None,
        device: str | None = None,
        batch_size: int = 16,
    ) -> None:
        self._model_path = Path(model_path or settings.remoteclip_model_path)
        self._expected_sha256 = expected_sha256 or settings.remoteclip_sha256
        self._batch_size = max(1, batch_size)
        self._model_name = "RemoteCLIP-ViT-L-14"
        self._dimension = settings.remoteclip_embedding_dim
        self._device_str = device or settings.device
        self._model: Any = None
        self._preprocess: Any = None
        self._tokenizer: Any = None
        self._actual_sha256: str | None = None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def checkpoint_hash(self) -> str | None:
        return self._actual_sha256

    def _ensure_loaded(self) -> None:
        """Lazily load RemoteCLIP model and preprocessing transforms."""
        if self._model is not None:
            return

        if not self._model_path.exists():
            log.error("RemoteCLIP checkpoint file not found", path=str(self._model_path))
            raise ModelMissingError(
                model_name=self._model_name,
                message=f"RemoteCLIP weights missing at '{self._model_path}'.",
                suggestion="Run `python scripts/download_models.py --remoteclip` to download.",
            )

        # Compute and verify SHA-256
        log.info("Verifying RemoteCLIP checkpoint checksum", path=str(self._model_path))
        hasher = hashlib.sha256()
        with open(self._model_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        self._actual_sha256 = hasher.hexdigest()

        if self._expected_sha256 and self._actual_sha256.lower() != self._expected_sha256.lower():
            raise ModelMissingError(
                model_name=self._model_name,
                message=f"RemoteCLIP SHA-256 mismatch: expected {self._expected_sha256}, got {self._actual_sha256}",
                suggestion="Re-download weights via `python scripts/download_models.py --remoteclip`.",
            )

        try:
            import torch
            import open_clip

            # Determine execution device
            if self._device_str.lower() == "cuda" and torch.cuda.is_available():
                target_device = "cuda"
            else:
                target_device = "cpu"

            log.info("Loading RemoteCLIP into memory", device=target_device, path=str(self._model_path))
            model, _, preprocess = open_clip.create_model_and_transforms("ViT-L-14")
            checkpoint = torch.load(str(self._model_path), map_location="cpu")
            if "state_dict" in checkpoint:
                checkpoint = checkpoint["state_dict"]
            model.load_state_dict(checkpoint)
            model.to(target_device)
            model.eval()

            self._model = model
            self._preprocess = preprocess
            self._tokenizer = open_clip.get_tokenizer("ViT-L-14")
            self._target_device = target_device
            log.info("RemoteCLIP loaded successfully", model=self._model_name, device=target_device)
        except ImportError as exc:
            log.error("PyTorch or open_clip not installed", error=str(exc))
            raise ModelMissingError(
                model_name=self._model_name,
                message=f"Dependencies missing for RemoteCLIP: {exc}",
                suggestion="Install torch and open-clip-torch via pip.",
            )
        except Exception as exc:
            log.error("Failed to load RemoteCLIP weights", error=str(exc))
            raise ModelMissingError(
                model_name=self._model_name,
                message=f"Failed loading RemoteCLIP checkpoint: {exc}",
                suggestion="Verify checkpoint integrity or re-download.",
            )

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
                try:
                    features = self._model.encode_text(tokens)
                except Exception as exc:
                    if "out of memory" in str(exc).lower() and batch_size > 1:
                        # Halve batch size and retry once on GPU OOM
                        log.warning("GPU OOM in text embedding; retrying with half batch", batch_size=batch_size)
                        torch.cuda.empty_cache()
                        features = self._retry_smaller_batches(batch, is_text=True)
                    else:
                        raise

            feat_np = features.cpu().numpy()
            all_embeddings.append(feat_np)

        combined = np.vstack(all_embeddings)
        return _normalize_l2(combined)

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
                try:
                    features = self._model.encode_image(batch_tensor)
                except Exception as exc:
                    if "out of memory" in str(exc).lower() and batch_size > 1:
                        log.warning("GPU OOM in image embedding; retrying with half batch", batch_size=batch_size)
                        torch.cuda.empty_cache()
                        features = self._retry_smaller_batches(batch_items, is_text=False)
                    else:
                        raise

            feat_np = features.cpu().numpy()
            all_embeddings.append(feat_np)

        combined = np.vstack(all_embeddings)
        return _normalize_l2(combined)

    def _retry_smaller_batches(self, items: list[Any], is_text: bool) -> Any:
        """Retry batch processing with batch_size=1 on OOM."""
        import torch

        sub_feats = []
        for item in items:
            if is_text:
                tok = self._tokenizer([item]).to(self._target_device)
                f = self._model.encode_text(tok)
            else:
                if isinstance(item, (str, Path)):
                    img = Image.open(item).convert("RGB")
                elif isinstance(item, np.ndarray):
                    img = Image.fromarray(item).convert("RGB")
                else:
                    img = item.convert("RGB")
                t = self._preprocess(img).unsqueeze(0).to(self._target_device)
                f = self._model.encode_image(t)
            sub_feats.append(f)
        return torch.cat(sub_feats, dim=0)


class DeterministicMockEmbeddingModel(EmbeddingModel):
    """
    Deterministic pseudo-embedding model for offline testing and development.
    Generates repeatable 768-dimensional float32 L2-normalized vectors
    without requiring heavy PyTorch weights downloads.
    """

    def __init__(self, dimension: int = 768) -> None:
        self._dimension = dimension
        self._model_name = "DeterministicMockRemoteCLIP"
        self._hash = "mock_sha256_synthetic_00000000"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def checkpoint_hash(self) -> str | None:
        return self._hash

    def embed_text(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        vectors = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            # Seed deterministic RNG with hash of string
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            vectors[i] = rng.randn(self._dimension).astype(np.float32)

        return _normalize_l2(vectors)

    def embed_images(self, images: Sequence[np.ndarray | Image.Image | str | Path]) -> np.ndarray:
        if not images:
            return np.empty((0, self._dimension), dtype=np.float32)

        vectors = np.zeros((len(images), self._dimension), dtype=np.float32)
        for i, item in enumerate(images):
            if isinstance(item, np.ndarray):
                digest = hashlib.sha256(item.tobytes()[:1024]).hexdigest()
            elif isinstance(item, (str, Path)):
                digest = hashlib.sha256(str(item).encode()).hexdigest()
            else:
                digest = hashlib.sha256(item.tobytes()[:1024]).hexdigest()
            seed = int(digest[:8], 16)
            rng = np.random.RandomState(seed)
            vectors[i] = rng.randn(self._dimension).astype(np.float32)

        return _normalize_l2(vectors)


# ---------------------------------------------------------------------------
# Global Singleton & Factory
# ---------------------------------------------------------------------------
_active_embedding_model: EmbeddingModel | None = None


def get_embedding_model(force_mock: bool = False) -> EmbeddingModel:
    """Retrieve the configured embedding model instance."""
    global _active_embedding_model

    if force_mock:
        return DeterministicMockEmbeddingModel(dimension=settings.remoteclip_embedding_dim)

    if _active_embedding_model is None:
        # Check if actual weights exist; fall back to deterministic mock if absent in dev mode
        model_path = Path(settings.remoteclip_model_path)
        if model_path.exists():
            _active_embedding_model = RemoteCLIPAdapter(
                model_path=model_path,
                expected_sha256=settings.remoteclip_sha256,
                device=settings.device,
                batch_size=settings.batch_size,
            )
        else:
            log.warning(
                "RemoteCLIP model weights not present on disk; initializing deterministic mock adapter",
                path=str(model_path),
            )
            _active_embedding_model = DeterministicMockEmbeddingModel(dimension=settings.remoteclip_embedding_dim)

    return _active_embedding_model
