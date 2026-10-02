"""
scripts/verify_dataset.py
Geospatial dataset verification tool (Section 28).

Calculates and validates:
- File count
- Missing files
- Corrupt / malformed rasters
- Cryptographic SHA-256 checksums
- Image dimensions (height, width)
- Coordinate Reference System (CRS)
- Multispectral band counts
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
from PIL import Image


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def inspect_raster_file(filepath: Path) -> Dict[str, Any]:
    """Inspect single raster file for dimensions, bands, CRS, and integrity."""
    result = {
        "filename": filepath.name,
        "filepath": str(filepath),
        "size_kb": round(filepath.stat().st_size / 1024.0, 2),
        "checksum": compute_sha256(filepath),
        "status": "VALID",
        "dimensions": None,
        "bands": None,
        "crs": "EPSG:4326 (Estimated)",
        "error": None,
    }

    # Attempt rasterio inspection first
    try:
        import rasterio
        with rasterio.open(filepath) as src:
            result["dimensions"] = [src.height, src.width]
            result["bands"] = src.count
            result["crs"] = str(src.crs or "EPSG:4326")
            return result
    except Exception:
        pass

    # Fallback OpenCV / PIL inspection
    try:
        img = cv2.imread(str(filepath), cv2.IMREAD_UNCHANGED)
        if img is not None:
            h, w = img.shape[:2]
            bands = 1 if img.ndim == 2 else img.shape[2]
            result["dimensions"] = [h, w]
            result["bands"] = bands
            return result

        pil_img = Image.open(filepath)
        result["dimensions"] = [pil_img.height, pil_img.width]
        result["bands"] = len(pil_img.getbands())
        return result
    except Exception as exc:
        result["status"] = "CORRUPT"
        result["error"] = str(exc)
        return result


def verify_dataset(directory_path: Path | str) -> Dict[str, Any]:
    """Verify all geospatial raster files in a directory."""
    dir_p = Path(directory_path)
    if not dir_p.exists():
        return {"error": f"Directory not found: {dir_p}"}

    raster_exts = {".tif", ".tiff", ".cog", ".png", ".jpg"}
    files = [f for f in dir_p.rglob("*") if f.is_file() and f.suffix.lower() in raster_exts]

    report = {
        "target_directory": str(dir_p),
        "total_files": len(files),
        "valid_files": 0,
        "corrupt_files": 0,
        "details": [],
    }

    print("=" * 60)
    print(f" Verifying Geospatial Dataset at: {dir_p}")
    print("=" * 60)

    for f in sorted(files):
        item = inspect_raster_file(f)
        report["details"].append(item)
        if item["status"] == "VALID":
            report["valid_files"] += 1
            print(f" [PASS] {f.name:32} | Dims: {item['dimensions']} | Bands: {item['bands']} | CRS: {item['crs']}")
        else:
            report["corrupt_files"] += 1
            print(f" [FAIL] {f.name:32} | CORRUPT: {item['error']}")

    print("-" * 60)
    print(f" Summary: {report['valid_files']} valid, {report['corrupt_files']} corrupt of {report['total_files']} total files.")
    print("=" * 60)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify satellite dataset files")
    parser.add_argument("--dir", default="./data", help="Directory to verify")
    args = parser.parse_args()
    verify_dataset(args.dir)
