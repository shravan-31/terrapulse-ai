"""
backend/tests/unit/test_settings.py
Tests for Pydantic settings validation.
"""

from __future__ import annotations

import json
import pytest


def make_env(overrides: dict = {}) -> dict:
    """Return a minimal valid env dict."""
    base = {
        "APP_ENV": "development",
        "DATA_MODE": "online",
        "OPERATOR_USERNAME": "analyst",
        "OPERATOR_PASSWORD": "strongpassword123",
        "SECRET_KEY": "a" * 64,
        "DATABASE_URL": "postgresql+asyncpg://postgres:pass@localhost/satquery",
        "POSTGRES_PASSWORD": "pass",
        "REDIS_URL": "redis://localhost:6379/0",
    }
    base.update(overrides)
    return base


def test_settings_load_minimal(monkeypatch):
    for k, v in make_env().items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    s = Settings(_env_file=None)
    assert s.app_env == "development"
    assert s.tile_size == 256
    assert s.min_change_area_m2 == 900.0
    assert s.min_change_pixels == 9


def test_settings_missing_required_var(monkeypatch):
    env = make_env()
    env.pop("OPERATOR_PASSWORD")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("OPERATOR_PASSWORD", raising=False)

    from app.core.settings import Settings
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_production_rejects_weak_password(monkeypatch):
    env = make_env({"APP_ENV": "production", "OPERATOR_PASSWORD": "changeme_strong_password"})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    with pytest.raises(Exception, match="Insecure"):
        Settings(_env_file=None)


def test_production_rejects_short_secret_key(monkeypatch):
    env = make_env({"APP_ENV": "production", "SECRET_KEY": "short"})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_confidence_weights_parse_from_json_string(monkeypatch):
    weights = {"valid_ratio": 0.5, "model_score": 0.5}
    env = make_env({"CONFIDENCE_WEIGHTS": json.dumps(weights)})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    s = Settings(_env_file=None)
    assert s.confidence_weights["valid_ratio"] == 0.5


def test_confidence_weights_sum_over_one_rejected(monkeypatch):
    weights = {"valid_ratio": 0.8, "model_score": 0.8}  # sum = 1.6 > 1.0
    env = make_env({"CONFIDENCE_WEIGHTS": json.dumps(weights)})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    with pytest.raises(Exception, match="weight"):
        Settings(_env_file=None)


def test_groq_available_when_key_set(monkeypatch):
    env = make_env({"GROQ_API_KEY": "gsk_testkey"})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    s = Settings(_env_file=None)
    assert s.groq_available is True


def test_groq_unavailable_when_key_missing(monkeypatch):
    env = make_env()
    env.pop("GROQ_API_KEY", None)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from app.core.settings import Settings
    s = Settings(_env_file=None)
    assert s.groq_available is False


def test_allowed_origins_parsed_from_comma_string(monkeypatch):
    env = make_env({"ALLOWED_ORIGINS": "http://localhost:5173,http://localhost:3000"})
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from app.core.settings import Settings
    s = Settings(_env_file=None)
    assert "http://localhost:5173" in s.allowed_origins
    assert "http://localhost:3000" in s.allowed_origins
