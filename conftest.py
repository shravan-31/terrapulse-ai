"""
Root conftest.py for the SatQuery AI monorepo.

Adds backend/ to sys.path so that `app.*` imports resolve when pytest
is run from the workspace root (d:\final sih) rather than from backend/.

Usage from workspace root (PowerShell):
    python -m pytest backend/tests/unit/test_settings.py -v
    python -m pytest backend/tests/ -v
"""

import sys
from pathlib import Path

# Add backend/ directory to sys.path so 'from app.xxx import ...' resolves
backend_dir = Path(__file__).parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
