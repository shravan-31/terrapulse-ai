"""
backend/tests/conftest.py
Root conftest for the backend test suite.

Provides:
- Isolation of pydantic-settings from the real .env file in settings tests.
  pytest-monkeypatch undoes env changes after each test, but module-level
  caching of the Settings class (not the singleton) is safe because each
  Settings(_env_file=None) call is a fresh instantiation.
- asyncio mode is set in pytest.ini (asyncio_mode = auto).
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_module():
    """
    Ensure that the app.core.settings module is NOT freshly reloaded between
    every test (that would break fixture caching), but DO guarantee that
    Settings() can be instantiated with _env_file=None independently of the
    module-level singleton.

    This fixture is intentionally a no-op beyond documentation. The real
    isolation mechanism is:
      1. Tests that need a clean Settings() call `Settings(_env_file=None)`
         with explicit monkeypatched env vars.
      2. The module-level `settings` singleton is loaded once from the real
         .env; tests that read it via `from app.core.settings import settings`
         read the real-environment object — that is intentional for auth tests.
    """
    yield
