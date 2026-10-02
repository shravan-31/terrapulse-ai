"""
backend/app/geospatial/tiling.py
Satellite image tiling and chunking service.

Implements:
- Sliding-window tiling (e.g., 512x512 tile size, 64px overlap)
- Preservation of geotransform and spatial bounding boxes per tile
- Saves individual tile images to disk (data/tiles/)
- Generates tile metadata records ready for database persistence and FAISS vector embedding
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

import cv2
import numpy as np
from PIL import Image
import structlog

from app.geospatial.raster import RasterMetadata

log = structlog.get_logger("satquery.geospatial.tiling")


@dataclass
class TileRecord:
    """Represents an extracted image tile with geospatial bounds."""
    tile_id: str
    scene_id: str
    x: int
    y: int
    width: int
    height: int
    bounds: list[float]  # [minx, miny, maxx, maxy] in WGS84
    image_path: str
    tile_array: np.ndarray


def create_tiles(
    image: np.ndarray,
    metadata: RasterMetadata,
    scene_id: str,
    output_dir: Path | str = "./data/tiles",
    tile_size: int = 512,
    overlap: int = 64,
) -> List[TileRecord]:
    """
    Split a large satellite scene into overlapping tiles.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    h, w = image.shape[:2]
    step = tile_size - overlap
    tiles: List[TileRecord] = []

    gt = metadata.geotransform  # (ox, px_w, 0, oy, 0, -px_h)

    for y0 in range(0, h, step):
        y1 = min(y0 + tile_size, h)
        if y1 - y0 < tile_size // 2 and tiles:
            continue  # skip tiny edge sliver if already covered

        for x0 in range(0, w, step):
            x1 = min(x0 + tile_size, w)
            if x1 - x0 < tile_size // 2 and tiles:
                continue

            tile_crop = image[y0:y1, x0:x1]
            actual_h, actual_w = tile_crop.shape[:2]

            # Calculate spatial bounds from geotransform
            min_lon = gt[0] + x0 * gt[1] + y1 * gt[2]
            max_lat = gt[3] + x0 * gt[4] + y0 * gt[5]
            max_lon = gt[0] + x1 * gt[1] + y0 * gt[2]
            min_lat = gt[3] + x1 * gt[4] + y1 * gt[5]
            bounds = [round(min_lon, 6), round(min_lat, 6), round(max_lon, 6), round(max_lat, 6)]

            tile_id = str(uuid.uuid4())
            tile_filename = f"{scene_id}_tile_{x0}_{y0}_{tile_id[:8]}.png"
            tile_filepath = out_dir / tile_filename

            # Save RGB tile image
            save_arr = tile_crop.copy()
            if save_arr.ndim == 2:
                save_arr = np.stack([save_arr] * 3, axis=-1)
            elif save_arr.ndim == 3 and save_arr.shape[2] > 3:
                save_arr = save_arr[:, :, :3]

            if save_arr.max() <= 1.0:
                save_arr = (save_arr * 255.0).astype(np.uint8)
            else:
                save_arr = save_arr.astype(np.uint8)

            Image.fromarray(save_arr).save(tile_filepath, format="PNG")

            tiles.append(
                TileRecord(
                    tile_id=tile_id,
                    scene_id=scene_id,
                    x=x0,
                    y=y0,
                    width=actual_w,
                    height=actual_h,
                    bounds=bounds,
                    image_path=str(tile_filepath),
                    tile_array=save_arr,
                )
            )

    log.info("Tiling completed", scene_id=scene_id, tile_count=len(tiles), tile_size=tile_size)
    return tiles
