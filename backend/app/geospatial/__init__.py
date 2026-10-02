"""
backend/app/geospatial/__init__.py
Geospatial processing package for TerraPulse AI.
"""

from app.geospatial.raster import read_raster, generate_thumbnail, RasterMetadata, compute_sha256
from app.geospatial.tiling import create_tiles, TileRecord
from app.geospatial.cloud_mask import process_cloud_masking, mask_clouds_scl, mask_clouds_spectral
from app.geospatial.alignment import align_temporal_images, AlignmentResult
from app.geospatial.geometry import create_geojson_feature, create_feature_collection, bbox_to_geojson_polygon, calculate_area_metrics

__all__ = [
    "read_raster",
    "generate_thumbnail",
    "RasterMetadata",
    "compute_sha256",
    "create_tiles",
    "TileRecord",
    "process_cloud_masking",
    "mask_clouds_scl",
    "mask_clouds_spectral",
    "align_temporal_images",
    "AlignmentResult",
    "create_geojson_feature",
    "create_feature_collection",
    "bbox_to_geojson_polygon",
    "calculate_area_metrics",
]
