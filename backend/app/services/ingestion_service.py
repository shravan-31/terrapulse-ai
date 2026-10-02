"""
backend/app/services/ingestion_service.py
End-to-end satellite imagery ingestion and processing service.

Pipeline:
Raster Upload -> Validate -> Metadata Extraction -> Cloud Masking ->
Tiling -> Embeddings -> FAISS Index -> Local STAC Catalog -> Database
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.geospatial.cloud_mask import process_cloud_masking
from app.geospatial.geometry import bbox_to_geojson_polygon
from app.geospatial.raster import generate_thumbnail, read_raster
from app.geospatial.tiling import create_tiles
from app.ml.encoders import get_encoder
from app.services.catalog_service import add_catalog_item
from app.services.faiss_service import get_index_manager

log = structlog.get_logger("satquery.services.ingestion")

DATA_DIR = Path("./data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TILES_DIR = DATA_DIR / "tiles"
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
MASKS_DIR = DATA_DIR / "masks"


def ensure_storage_dirs() -> None:
    """Ensure all required data directories exist."""
    for d in [RAW_DIR, PROCESSED_DIR, TILES_DIR, THUMBNAILS_DIR, MASKS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


async def ingest_raster_file(
    file_path: Path | str,
    sensor: str = "Sentinel-2",
    acquisition_date: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Ingest, preprocess, tile, embed, and index a single satellite raster.
    """
    ensure_storage_dirs()
    src_path = Path(file_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Source raster not found at '{src_path}'")

    scene_id = f"{sensor.lower()}_{src_path.stem}_{uuid.uuid4().hex[:6]}"
    log.info("Starting ingestion pipeline", scene_id=scene_id, file=str(src_path))

    # 1. Read raster and extract metadata
    data, meta = read_raster(src_path)
    if acquisition_date:
        meta.acquisition_date = acquisition_date
    else:
        meta.acquisition_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    meta.sensor = sensor

    # 2. Cloud masking
    raw_img, cloud_mask, cleaned_img, cloud_pct = process_cloud_masking(
        raw_image=data,
        output_dir=MASKS_DIR,
        scene_id=scene_id,
    )
    meta.cloud_percentage = cloud_pct if isinstance(cloud_pct, (int, float)) else 0.0

    # 3. Generate thumbnail
    thumb_path = THUMBNAILS_DIR / f"{scene_id}_thumbnail.png"
    generate_thumbnail(cleaned_img, thumb_path, max_size=512)

    # 4. Generate tiles
    tiles = create_tiles(
        image=cleaned_img,
        metadata=meta,
        scene_id=scene_id,
        output_dir=TILES_DIR,
        tile_size=512,
        overlap=64,
    )

    # 5. Extract embeddings and add to FAISS
    encoder = get_encoder()
    index_mgr = get_index_manager()

    tile_arrays = [t.tile_array for t in tiles]
    embeddings = encoder.embed_images(tile_arrays)

    vector_ids = []
    for i, t in enumerate(tiles):
        # Generate stable int64 vector ID using lower 63 bits of UUID
        v_id = uuid.uuid4().int & 0x7FFFFFFFFFFFFFFF
        vector_ids.append(v_id)

    # Add to FAISS index
    if vector_ids:
        index_mgr.index.add(vector_ids=vector_ids, vectors=embeddings)

    # 6. Add to STAC Catalog
    stac_assets = {
        "visual": {"href": str(src_path), "type": "image/tiff", "title": "Raw Scene"},
        "thumbnail": {"href": str(thumb_path), "type": "image/png", "title": "Thumbnail"},
        "cloud_mask": {"href": str(MASKS_DIR / f"{scene_id}_cloud_mask.png"), "type": "image/png", "title": "Cloud Mask"},
    }

    catalog_item = add_catalog_item(
        item_id=scene_id,
        bbox=meta.bounds,
        datetime_iso=f"{meta.acquisition_date}T00:00:00Z",
        platform=sensor,
        instruments=[sensor],
        assets=stac_assets,
        projection=meta.crs,
        resolution_m=float(meta.resolution[0]),
        cloud_cover=meta.cloud_percentage,
        properties_extra={
            "tile_count": len(tiles),
            "checksum_sha256": meta.checksum,
        },
    )

    log.info(
        "Ingestion pipeline finished successfully",
        scene_id=scene_id,
        tile_count=len(tiles),
        cloud_percentage=meta.cloud_percentage,
    )

    return {
        "scene_id": scene_id,
        "metadata": meta.to_dict(),
        "tile_count": len(tiles),
        "thumbnail_url": f"/api/rasters/{scene_id}/thumbnail.png",
        "cloud_percentage": meta.cloud_percentage,
        "catalog_item_id": catalog_item["id"],
        "status": "COMPLETED",
    }
