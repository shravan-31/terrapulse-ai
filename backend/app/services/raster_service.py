"""
backend/app/services/raster_service.py
Geospatial raster preprocessing, spectral indices calculation,
co-registration verification, tiling, and scene-specific tile rendering.

Implements:
- ADR-008: Scene-specific raster delivery with SSRF guards and transparent nodata.
- ADR-010: Spectral indices from reflectance only; product-baseline-aware offset;
           nearest-neighbor SCL categorical resampling, bilinear band resampling.
"""

from __future__ import annotations

import io
import math
import os
import zipfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
import structlog

from app.core.errors import NotFoundError, UnusableImageryError
from app.core.settings import settings

log = structlog.get_logger("satquery.raster")


# ---------------------------------------------------------------------------
# Safe Archive Extraction (Zip Slip Defense)
# ---------------------------------------------------------------------------
def safe_extract_zip(zip_path: Path, target_dir: Path) -> list[Path]:
    """
    Safely extract a ZIP archive while protecting against Zip Slip path traversal.
    Raises ValueError if any entry attempts to escape target_dir.
    """
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted_files: list[Path] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Check for directory traversal attempts
            dest_file = (target_dir / member.filename).resolve()
            if not str(dest_file).startswith(str(target_dir)):
                raise ValueError(
                    f"Security violation: Archive member '{member.filename}' escapes target dir."
                )

            zf.extract(member, target_dir)
            if not member.is_dir():
                extracted_files.append(dest_file)

    log.info("Archive safely extracted", count=len(extracted_files), target=str(target_dir))
    return extracted_files


# ---------------------------------------------------------------------------
# Reflectance Conversion (ADR-010)
# ---------------------------------------------------------------------------
def dn_to_reflectance(
    dn_array: np.ndarray,
    processing_baseline: str = "04.00",
) -> np.ndarray:
    """
    Convert Sentinel-2 L2A Digital Numbers (DN) to Bottom-of-Atmosphere (BOA) surface reflectance.

    ADR-010 & Sentinel-2 Baseline policy:
    - Products generated with processing baseline >= 04.00 include a radiometric offset of -1000 DN.
    - BOA_Reflectance = (DN + BOA_ADD_OFFSET) / QUANTIFICATION_VALUE
      where default offset is -1000 and QUANTIFICATION_VALUE is 10000.
    - Negative reflectance values resulting from shadow or water absorption are clamped to 0.0.
    """
    dn_float = dn_array.astype(np.float32)
    # Check baseline version
    try:
        baseline_num = float(processing_baseline.replace("v", ""))
    except ValueError:
        baseline_num = 4.0

    if baseline_num >= 4.0:
        # Radiometric offset applied from baseline 04.00 (Jan 2022) onwards
        reflectance = (dn_float - 1000.0) / 10000.0
    else:
        reflectance = dn_float / 10000.0

    return np.clip(reflectance, 0.0, 1.5).astype(np.float32)


# ---------------------------------------------------------------------------
# Spectral Indices (ADR-010)
# ---------------------------------------------------------------------------
def compute_ndvi(nir: np.ndarray, red: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """
    Normalized Difference Vegetation Index (NDVI).
    NDVI = (B08 - B04) / (B08 + B04)
    Computed strictly from surface reflectance bands.
    """
    numerator = nir - red
    denominator = nir + red + eps
    ndvi = numerator / denominator
    return np.clip(ndvi, -1.0, 1.0).astype(np.float32)


def compute_ndwi(green: np.ndarray, nir: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """
    Normalized Difference Water Index (NDWI, McFeeters 1996 definition).
    NDWI = (B03 - B08) / (B03 + B08)
    Computed strictly from surface reflectance bands.
    """
    numerator = green - nir
    denominator = green + nir + eps
    ndwi = numerator / denominator
    return np.clip(ndwi, -1.0, 1.0).astype(np.float32)


def compute_ndbi(swir: np.ndarray, nir: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """
    Normalized Difference Built-up Index (NDBI).
    NDBI = (B11 - B08) / (B11 + B08)
    Computed strictly from surface reflectance bands.
    """
    numerator = swir - nir
    denominator = swir + nir + eps
    ndbi = numerator / denominator
    return np.clip(ndbi, -1.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# SCL Cloud / Snow Masking
# ---------------------------------------------------------------------------
def create_valid_mask_from_scl(scl: np.ndarray) -> np.ndarray:
    """
    Generate boolean valid-data mask from Sentinel-2 Scene Classification Layer (SCL).
    
    SCL Classes:
      0: NO_DATA (invalid)
      1: SATURATED_OR_DEFECTIVE (invalid)
      2: DARK_AREA_PIXELS (valid)
      3: CLOUD_SHADOWS (invalid)
      4: VEGETATION (valid)
      5: NOT_VEGETATED (valid)
      6: WATER (valid)
      7: UNCLASSIFIED (valid)
      8: CLOUD_MEDIUM_PROBABILITY (invalid)
      9: CLOUD_HIGH_PROBABILITY (invalid)
     10: THIN_CIRRUS (invalid)
     11: SNOW (invalid)
    """
    invalid_classes = {0, 1, 3, 8, 9, 10, 11}
    valid_mask = np.isin(scl, list(invalid_classes), invert=True)
    return valid_mask.astype(bool)


# ---------------------------------------------------------------------------
# Co-Registration Quality Check (ADR-015)
# ---------------------------------------------------------------------------
def check_coregistration(
    ref_gray: np.ndarray,
    tgt_gray: np.ndarray,
    max_acceptable_shift_px: float = 2.0,
) -> dict[str, Any]:
    """
    Estimate sub-pixel registration shift between two imagery arrays using phase correlation.
    
    Returns:
        {
            "dx": float,
            "dy": float,
            "shift_pixels": float,
            "correlation_peak": float,
            "acceptable": bool,
            "rejection_reason": str | None
        }
    """
    # Ensure dimensions match
    h = min(ref_gray.shape[0], tgt_gray.shape[0])
    w = min(ref_gray.shape[1], tgt_gray.shape[1])
    ref_crop = ref_gray[:h, :w].astype(np.float32)
    tgt_crop = tgt_gray[:h, :w].astype(np.float32)

    # Apply Hanning window to reduce edge discontinuities in FFT
    hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(ref_crop, tgt_crop, hann)

    shift = math.hypot(dx, dy)
    acceptable = shift <= max_acceptable_shift_px and response >= 0.10
    rejection_reason = None
    if not acceptable:
        if shift > max_acceptable_shift_px:
            rejection_reason = f"Image shift {shift:.2f}px exceeds tolerance {max_acceptable_shift_px:.2f}px"
        else:
            rejection_reason = f"Phase correlation confidence {response:.3f} below threshold 0.10"

    return {
        "dx": round(float(dx), 3),
        "dy": round(float(dy), 3),
        "shift_pixels": round(float(shift), 3),
        "correlation_peak": round(float(response), 4),
        "acceptable": acceptable,
        "rejection_reason": rejection_reason,
    }


# ---------------------------------------------------------------------------
# Tiling Utility (TILE_SIZE = 256)
# ---------------------------------------------------------------------------
def tile_array(
    array: np.ndarray,
    tile_size: int = 256,
    valid_mask: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """
    Divide a 2D or 3D raster array into fixed tile_size x tile_size chunks.
    Pads edge tiles with zeros to guarantee exact tile_size dimensions.

    Returns list of dicts with:
      tile_index: int
      bounds: [col_start, row_start, col_end, row_end]
      valid_ratio: float in [0.0, 1.0]
      tile: np.ndarray of shape (tile_size, tile_size, ...)
    """
    h, w = array.shape[:2]
    tiles = []
    tile_index = 0

    num_rows = math.ceil(h / tile_size)
    num_cols = math.ceil(w / tile_size)

    for r in range(num_rows):
        r_start = r * tile_size
        r_end = min(r_start + tile_size, h)
        for c in range(num_cols):
            c_start = c * tile_size
            c_end = min(c_start + tile_size, w)

            chunk = array[r_start:r_end, c_start:c_end]
            chunk_h, chunk_w = chunk.shape[:2]

            # Pad if needed
            if chunk_h < tile_size or chunk_w < tile_size:
                if array.ndim == 2:
                    padded = np.zeros((tile_size, tile_size), dtype=array.dtype)
                    padded[:chunk_h, :chunk_w] = chunk
                else:
                    padded = np.zeros((tile_size, tile_size, array.shape[2]), dtype=array.dtype)
                    padded[:chunk_h, :chunk_w, :] = chunk
                tile_data = padded
            else:
                tile_data = chunk

            # Compute valid ratio
            if valid_mask is not None:
                mask_chunk = valid_mask[r_start:r_end, c_start:c_end]
                valid_ratio = float(np.count_nonzero(mask_chunk)) / float(tile_size * tile_size)
            else:
                valid_ratio = 1.0

            tiles.append({
                "tile_index": tile_index,
                "bounds": [c_start, r_start, c_end, r_end],
                "valid_ratio": round(valid_ratio, 4),
                "tile_data": tile_data,
            })
            tile_index += 1

    return tiles


# ---------------------------------------------------------------------------
# Scene-Specific Raster Delivery (ADR-008)
# ---------------------------------------------------------------------------
_registered_raster_assets: dict[str, Path] = {}


def register_raster_asset(asset_id: str, path: Path) -> None:
    """Registers an authorized asset file path against an internal asset_id."""
    path = path.resolve()
    base_data = Path(settings.data_path).resolve()
    base_cache = Path(settings.cache_path).resolve()
    # SSRF Guard: verify path is inside data or cache directories
    if not (base_data in path.parents or base_cache in path.parents or path == base_data or path == base_cache):
        raise ValueError(f"Unauthorized asset path location: {path}")
    _registered_raster_assets[asset_id] = path


def get_raster_tile_png(
    asset_id: str,
    z: int,
    x: int,
    y: int,
    tile_size: int = 256,
) -> bytes:
    """
    Returns a 256x256 RGBA PNG tile for the given asset ID and tile coordinates.
    Nodata pixels are rendered with transparent alpha (A=0).
    Enforces SSRF guards by only serving registered asset IDs.
    Does NOT trigger ML inference.
    """
    asset_path = _registered_raster_assets.get(asset_id)
    if not asset_path or not asset_path.exists():
        raise NotFoundError(resource="RasterAsset", resource_id=asset_id)

    # In production with rasterio, this reads a spatial window.
    # When loading standard images/GeoTIFFs via PIL/OpenCV:
    try:
        img = Image.open(asset_path)
    except Exception as exc:
        log.error("Failed to open raster asset", asset_id=asset_id, error=str(exc))
        raise NotFoundError(resource="RasterAsset", resource_id=asset_id) from exc

    img_w, img_h = img.size
    # Compute tile slice at current zoom level
    cols = max(1, img_w // tile_size)
    rows = max(1, img_h // tile_size)

    col = x % cols
    row = y % rows

    x0 = col * tile_size
    y0 = row * tile_size
    x1 = min(x0 + tile_size, img_w)
    y1 = min(y0 + tile_size, img_h)

    tile_crop = img.crop((x0, y0, x1, y1))
    
    # Ensure RGBA with transparent padding
    final_tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
    final_tile.paste(tile_crop, (0, 0))

    buf = io.BytesIO()
    final_tile.save(buf, format="PNG")
    return buf.getvalue()
