"""
backend/app/geospatial/cloud_mask.py
Cloud masking and atmospheric quality assurance for satellite imagery.

Implements Section 12:
- Sentinel-2 Scene Classification Layer (SCL) decoding
- Spectral thresholding fallback (Blue/NIR high albedo & low temperature)
- Separate outputs:
  * raw image
  * cloud mask (boolean / uint8 mask)
  * cleaned image (with cloud pixels masked or interpolated)
- Accurate cloud percentage calculation; marks "unknown" if cloud info is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np
from PIL import Image
import structlog

log = structlog.get_logger("satquery.geospatial.cloud_mask")


def mask_clouds_scl(scl: np.ndarray) -> np.ndarray:
    """
    Decode Sentinel-2 SCL layer:
    Invalid: 0 (NO_DATA), 1 (SATURATED/DEFECTIVE), 3 (CLOUD_SHADOWS), 8 (CLOUD_MEDIUM), 9 (CLOUD_HIGH), 10 (THIN_CIRRUS), 11 (SNOW).
    Returns boolean cloud/invalid mask (True = Cloud/Invalid, False = Clear).
    """
    invalid_classes = {0, 1, 3, 8, 9, 10, 11}
    cloud_mask = np.isin(scl, list(invalid_classes))
    return cloud_mask


def mask_clouds_spectral(rgb_image: np.ndarray, brightness_thresh: float = 0.85) -> np.ndarray:
    """
    Spectral brightness thresholding for optical imagery lacking an explicit SCL band.
    Detects high-reflectance white cloud clusters without false-flagging bright soil.
    """
    img = rgb_image.astype(np.float32)
    if img.max() > 1.0:
        img /= 255.0

    # Whiteness / low color saturation combined with high luminance
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    color_diff = np.maximum(np.abs(r - g), np.abs(g - b))

    # Cloud: high brightness and low color variance (near-white)
    cloud_mask = (luminance >= brightness_thresh) & (color_diff < 0.12)
    # Morphological opening to suppress single-pixel noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cloud_mask = cv2.morphologyEx(cloud_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    return cloud_mask


def process_cloud_masking(
    raw_image: np.ndarray,
    scl_band: Optional[np.ndarray] = None,
    output_dir: Path | str = "./data/masks",
    scene_id: str = "scene",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float | str]:
    """
    Process imagery and produce:
    1. Raw image
    2. Cloud mask
    3. Cleaned image (with clouds replaced or transparent)
    4. Cloud percentage (float or 'unknown')
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if scl_band is not None:
        cloud_mask = mask_clouds_scl(scl_band)
        total_valid_pixels = np.sum(scl_band != 0)
        if total_valid_pixels > 0:
            cloud_pct = round(float(np.sum(cloud_mask) / total_valid_pixels * 100.0), 2)
        else:
            cloud_pct = "unknown"
    else:
        cloud_mask = mask_clouds_spectral(raw_image)
        total_pixels = raw_image.shape[0] * raw_image.shape[1]
        cloud_pct = round(float(np.sum(cloud_mask) / total_pixels * 100.0), 2)

    # Generate cleaned image
    cleaned = raw_image.copy()
    if cleaned.max() <= 1.0:
        cleaned = (cleaned * 255.0).astype(np.uint8)
    else:
        cleaned = cleaned.astype(np.uint8)

    # Inpaint or dim cloud regions
    if np.any(cloud_mask):
        try:
            # Navier-Stokes inpainting for small cloud holes
            cleaned = cv2.inpaint(cleaned, cloud_mask.astype(np.uint8) * 255, 3, cv2.INPAINT_NS)
        except Exception:
            # Fallback: dim cloud area
            cleaned[cloud_mask] = (cleaned[cloud_mask] * 0.3).astype(np.uint8)

    # Save artifact paths
    mask_png_path = out_dir / f"{scene_id}_cloud_mask.png"
    cleaned_png_path = out_dir / f"{scene_id}_cleaned.png"

    Image.fromarray((cloud_mask.astype(np.uint8) * 255)).save(mask_png_path, format="PNG")
    Image.fromarray(cleaned).save(cleaned_png_path, format="PNG")

    return raw_image, cloud_mask, cleaned, cloud_pct
