"""
backend/tests/unit/test_raster.py
Unit tests for raster preprocessing, spectral indices calculation (ADR-010),
coregistration checking, and raster delivery (ADR-008).
"""

import io
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.core.errors import NotFoundError
from app.services.raster_service import (
    check_coregistration,
    compute_ndbi,
    compute_ndvi,
    compute_ndwi,
    create_valid_mask_from_scl,
    dn_to_reflectance,
    get_raster_tile_png,
    register_raster_asset,
    safe_extract_zip,
    tile_array,
)


def test_dn_to_reflectance_baseline_offset():
    # Test Baseline >= 04.00 (with -1000 offset)
    dn = np.array([1000, 2000, 5000], dtype=np.uint16)
    ref = dn_to_reflectance(dn, processing_baseline="04.00")
    # (1000 - 1000) / 10000 = 0.0
    assert pytest.approx(ref[0], abs=1e-5) == 0.0
    # (2000 - 1000) / 10000 = 0.1
    assert pytest.approx(ref[1], abs=1e-5) == 0.1
    # (5000 - 1000) / 10000 = 0.4
    assert pytest.approx(ref[2], abs=1e-5) == 0.4

    # Test Baseline < 04.00 (no offset)
    ref_old = dn_to_reflectance(dn, processing_baseline="03.01")
    assert pytest.approx(ref_old[0], abs=1e-5) == 0.1


def test_spectral_indices_calculations():
    # Pure vegetation: NIR high, Red low
    nir = np.array([0.8, 0.1], dtype=np.float32)
    red = np.array([0.1, 0.1], dtype=np.float32)
    ndvi = compute_ndvi(nir, red)
    assert ndvi[0] > 0.7  # High vegetation signal
    assert pytest.approx(ndvi[1], abs=1e-4) == 0.0  # Equal values -> 0

    # Water index: Green high, NIR low
    green = np.array([0.4], dtype=np.float32)
    nir_water = np.array([0.05], dtype=np.float32)
    ndwi = compute_ndwi(green, nir_water)
    assert ndwi[0] > 0.6  # High water signal

    # Built-up index: SWIR high, NIR moderate
    swir = np.array([0.5], dtype=np.float32)
    nir_built = np.array([0.2], dtype=np.float32)
    ndbi = compute_ndbi(swir, nir_built)
    assert ndbi[0] > 0.4


def test_scl_valid_mask():
    # Classes: 4 (veg - valid), 6 (water - valid), 3 (shadow - invalid), 9 (cloud - invalid)
    scl = np.array([[4, 6], [3, 9]], dtype=np.uint8)
    mask = create_valid_mask_from_scl(scl)
    assert mask[0, 0] is True or mask[0, 0] == 1
    assert mask[0, 1] is True or mask[0, 1] == 1
    assert mask[1, 0] is False or mask[1, 0] == 0
    assert mask[1, 1] is False or mask[1, 1] == 0


def test_tile_array_padding_and_bounds():
    # Non-multiple of 256 (300 x 300)
    arr = np.ones((300, 300), dtype=np.float32)
    tiles = tile_array(arr, tile_size=256)
    # Should yield 4 tiles (2x2 grid)
    assert len(tiles) == 4
    for t in tiles:
        # Padded to exact tile_size x tile_size
        assert t["tile_data"].shape == (256, 256)
    # First tile top-left bounds
    assert tiles[0]["bounds"] == [0, 0, 256, 256]


def test_coregistration_check():
    # Identical images should show ~0 shift and high correlation peak
    ref = np.random.randint(0, 255, size=(128, 128), dtype=np.uint8)
    res = check_coregistration(ref, ref)
    assert res["shift_pixels"] < 0.5
    assert res["acceptable"] is True


def test_safe_extract_zip_rejects_path_traversal(tmp_path):
    # Construct a ZIP containing path traversal entry "../evil.txt"
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "attack payload")

    dest_dir = tmp_path / "extract_dir"
    with pytest.raises(ValueError, match="Security violation"):
        safe_extract_zip(zip_path, dest_dir)


def test_raster_delivery_ssrf_guard(tmp_path):
    # Registering outside data/cache must be rejected
    unauthorized_path = tmp_path.parent / "secret.png"
    with pytest.raises(ValueError, match="Unauthorized asset path"):
        register_raster_asset("leak_asset", unauthorized_path)


def test_raster_tile_png_rendering(tmp_path):
    # Create valid dummy PNG image in cache directory
    from app.core.settings import settings
    settings.cache_path = str(tmp_path)
    settings.data_path = str(tmp_path)

    test_img = Image.new("RGBA", (512, 512), (255, 0, 0, 255))
    img_path = tmp_path / "asset_1.png"
    test_img.save(img_path)

    register_raster_asset("asset_1", img_path)
    tile_png = get_raster_tile_png("asset_1", z=10, x=0, y=0, tile_size=256)
    
    assert len(tile_png) > 0
    # Verify valid PNG header bytes
    assert tile_png[:8] == b"\x89PNG\r\n\x1a\n"
