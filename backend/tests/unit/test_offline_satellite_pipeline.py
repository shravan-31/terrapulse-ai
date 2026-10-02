"""
backend/tests/unit/test_offline_satellite_pipeline.py
Unit tests for offline satellite intelligence pipeline.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pytest

from app.geospatial.alignment import align_temporal_images
from app.geospatial.cloud_mask import process_cloud_masking
from app.geospatial.geometry import calculate_area_metrics, create_feature_collection
from app.geospatial.raster import generate_thumbnail, read_raster
from app.geospatial.tiling import create_tiles
from app.ml.change_detection.classical_detector import ClassicalSpectralChangeDetector
from app.ml.encoders import get_encoder
from app.services.catalog_service import add_catalog_item, get_catalog_item
from app.services.faiss_service import get_index_manager
from app.services.report_service import generate_pdf_report
from scripts.create_demo_dataset import generate_synthetic_sentinel2_pair


@pytest.fixture
def demo_pair(tmp_path: Path):
    t1, t2 = generate_synthetic_sentinel2_pair(output_dir=tmp_path)
    return t1, t2


def test_raster_ingestion_and_metadata(demo_pair):
    t1_path, _ = demo_pair
    data, meta = read_raster(t1_path)
    assert data.shape[:2] == (1024, 1024)
    assert meta.bands in (1, 3, 4)
    assert meta.crs is not None
    assert len(meta.bounds) == 4
    assert len(meta.checksum) == 64


def test_cloud_masking(demo_pair):
    t1_path, _ = demo_pair
    data, _ = read_raster(t1_path)
    raw, mask, cleaned, cloud_pct = process_cloud_masking(data, scene_id="test_unit")
    assert mask.shape == data.shape[:2]
    assert cleaned.shape == data.shape


def test_tiling(demo_pair, tmp_path):
    t1_path, _ = demo_pair
    data, meta = read_raster(t1_path)
    tiles = create_tiles(data, meta, scene_id="unit_s2", output_dir=tmp_path / "tiles", tile_size=512, overlap=64)
    assert len(tiles) >= 4
    for t in tiles:
        assert Path(t.image_path).exists()
        assert len(t.bounds) == 4


def test_encoder_and_faiss():
    encoder = get_encoder()
    assert encoder.dimension == 768

    sample_query = ["solar park in desert", "water reservoir"]
    text_embeddings = encoder.embed_text(sample_query)
    assert text_embeddings.shape == (2, 768)

    # Check L2 normalization
    norms = np.linalg.norm(text_embeddings, axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-3)

    # FAISS search
    index_mgr = get_index_manager()
    v_ids = [99901, 99902]
    index_mgr.index.add(vector_ids=v_ids, vectors=text_embeddings)

    scores, matched_ids = index_mgr.index.search(text_embeddings[0], top_k=2)
    assert len(matched_ids) > 0


def test_change_detection(demo_pair):
    t1_path, t2_path = demo_pair
    img1, meta1 = read_raster(t1_path)
    img2, _ = read_raster(t2_path)

    detector = ClassicalSpectralChangeDetector()
    res = detector.detect_changes(
        t1_image=img1,
        t2_image=img2,
        pixel_resolution_m=10.0,
        threshold=0.45,
        min_area_m2=900.0,
        geotransform=meta1.geotransform,
    )
    assert res.total_change_area_m2 > 0
    assert res.percentage_change > 0
    assert len(res.components) > 0
    assert res.primary_change_type in [
        "construction",
        "urban expansion",
        "vegetation loss",
        "vegetation growth",
        "road development",
        "water change",
        "land-use change",
        "Unknown / Needs Review",
    ]


def test_stac_catalog():
    item = add_catalog_item(
        item_id="unit_test_item_001",
        bbox=[71.90, 27.50, 71.95, 27.55],
        datetime_iso="2024-05-10T00:00:00Z",
        platform="Sentinel-2",
        instruments=["MSI"],
        assets={"visual": {"href": "/data/test.tif"}},
    )
    assert item["id"] == "unit_test_item_001"

    retrieved = get_catalog_item("unit_test_item_001")
    assert retrieved is not None
    assert retrieved["id"] == "unit_test_item_001"


def test_report_generation(tmp_path):
    pdf = generate_pdf_report(
        report_id="UNIT-TEST-001",
        title="Unit Test Intelligence Report",
        location_name="Test Complex",
        coordinates=[27.53, 71.91],
        aoi_bounds=[71.86, 27.48, 71.96, 27.58],
        before_date="2024-05-10",
        after_date="2026-04-15",
        sensor="Sentinel-2",
        methodology="Spectral Delta Test",
        total_change_area_m2=50000.0,
        percentage_change=5.2,
        confidence_score=0.92,
        change_type="construction",
        review_status="confirmed_by_analyst",
    )
    assert Path(pdf).exists()
