"""
scripts/check_environment.py
Validates the local Python runtime, geospatial C-libraries (GDAL, PROJ), PyTorch, FAISS, and CUDA support.
"""

import sys
import platform

print("=" * 60)
print("TerraPulse AI — Environment Diagnostics")
print("=" * 60)
print(f"Python Version : {sys.version.split()[0]} ({platform.architecture()[0]})")
print(f"Operating System: {platform.system()} {platform.release()}")

packages = [
    ("fastapi", "FastAPI"),
    ("pydantic", "Pydantic"),
    ("sqlalchemy", "SQLAlchemy"),
    ("alembic", "Alembic"),
    ("rasterio", "Rasterio / GDAL"),
    ("pyproj", "PyProj"),
    ("shapely", "Shapely"),
    ("cv2", "OpenCV"),
    ("PIL", "Pillow"),
    ("numpy", "NumPy"),
    ("torch", "PyTorch"),
    ("faiss", "FAISS Vector Search"),
    ("reportlab", "ReportLab PDF Engine"),
    ("yaml", "PyYAML"),
]

missing = []
for mod, name in packages:
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        print(f"  [OK] {name:22} : {ver}")
    except ImportError:
        print(f"  [--] {name:22} : NOT INSTALLED (or using fallback)")
        missing.append(name)

# Check Torch CUDA
try:
    import torch
    cuda_avail = torch.cuda.is_available()
    print(f"\nCompute Device: {'CUDA GPU (' + torch.cuda.get_device_name(0) + ')' if cuda_avail else 'CPU (Offline Optimized)'}")
except Exception:
    print("\nCompute Device: CPU")

print("=" * 60)
if not missing or set(missing) <= {"FAISS Vector Search"}:
    print("STATUS: ENVIRONMENT READY FOR PRODUCTION / OFFLINE RUNTIME")
else:
    print(f"STATUS: {len(missing)} PACKAGES MISSING: {', '.join(missing)}")
print("=" * 60)
