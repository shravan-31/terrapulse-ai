"""
backend/app/ml/encoders/__init__.py
Encoder factory and registry for satellite vision-language embeddings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import structlog

from app.core.settings import settings
from app.ml.encoders.base_encoder import BaseEncoder
from app.ml.encoders.remoteclip_encoder import RemoteCLIPEncoder
from app.ml.encoders.openclip_encoder import OpenCLIPEncoder
from app.ml.encoders.clip_encoder import DeterministicOfflineEncoder

log = structlog.get_logger("satquery.ml.encoders")

_active_encoder: Optional[BaseEncoder] = None


def get_encoder(provider: str | None = None, force_offline: bool = False) -> BaseEncoder:
    """
    Factory to retrieve or initialize the configured satellite encoder.
    Automatically detects available models and falls back cleanly.
    """
    global _active_encoder

    if force_offline:
        return DeterministicOfflineEncoder(dimension=settings.remoteclip_embedding_dim)

    if _active_encoder is not None and (provider is None or _active_encoder.model_name.lower().startswith(provider.lower())):
        return _active_encoder

    chosen_provider = provider or getattr(settings, "embedding_provider", "remoteclip")

    # 1. Try RemoteCLIP if requested
    if chosen_provider.lower() == "remoteclip":
        model_path = Path(settings.remoteclip_model_path)
        encoder = RemoteCLIPEncoder(
            model_path=model_path,
            device=settings.device,
            batch_size=settings.batch_size,
        )
        if encoder.is_available:
            _active_encoder = encoder
            log.info("Initialized RemoteCLIP encoder", path=str(model_path))
            return _active_encoder
        else:
            log.warning("RemoteCLIP weights not present or torch missing; falling back to deterministic encoder", path=str(model_path))

    # 2. Try OpenCLIP if requested
    elif chosen_provider.lower() == "openclip":
        encoder = OpenCLIPEncoder(device=settings.device, batch_size=settings.batch_size)
        if encoder.is_available:
            _active_encoder = encoder
            log.info("Initialized OpenCLIP encoder")
            return _active_encoder
        else:
            log.warning("OpenCLIP dependencies not available; falling back to deterministic encoder")

    # 3. Deterministic offline fallback (never crashes, guarantees finite 768-dim normalized vectors)
    log.info("Using DeterministicOfflineEncoder for vector indexing and search")
    _active_encoder = DeterministicOfflineEncoder(dimension=settings.remoteclip_embedding_dim)
    return _active_encoder
