"""
backend/app/core/config.py
Central Configuration Manager for TerraPulse AI / SatQuery AI.
Loads YAML configuration, handles device selection (auto, cpu, cuda), and re-exports Pydantic settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
import yaml

from app.core.settings import settings

_CONFIG_SEARCH_PATHS = [
    Path("config/config.yaml"),
    Path("../config/config.yaml"),
    Path(__file__).parent.parent.parent.parent / "config" / "config.yaml",
    Path("config.yaml"),
    Path("../config.yaml"),
    Path(__file__).parent.parent.parent.parent / "config.yaml",
]


def load_yaml_config() -> Dict[str, Any]:
    """Search and load central YAML configuration file."""
    for p in _CONFIG_SEARCH_PATHS:
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
    return {}


app_config = load_yaml_config()


def get_compute_device(requested: str = "auto") -> str:
    """Resolve compute device based on availability (auto, cpu, cuda)."""
    req = requested.lower()
    if req == "cpu":
        return "cpu"
    if req in ("cuda", "gpu"):
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
    # Auto
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


__all__ = ["settings", "app_config", "load_yaml_config", "get_compute_device"]
