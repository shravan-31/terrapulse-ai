"""
backend/app/repositories/scene_repository.py
SQLAlchemy / PostGIS persistence repository for Scenes, SceneAssets, and Tiles.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import Scene, SceneAsset, Tile


class SceneRepository:
    """Handles database persistence for Scene, SceneAsset, and Tile entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_scene(
        self,
        product_id: str,
        acquisition_at: datetime,
        cloud_coverage_percent: float,
        footprint: dict[str, Any],
        provider: str = "copernicus",
        crs: str = "EPSG:4326",
        metadata_json: dict[str, Any] | None = None,
        scene_id: uuid.UUID | None = None,
    ) -> Scene:
        """Create and persist a new satellite Scene record."""
        scene_uuid = scene_id or uuid.uuid4()
        scene = Scene(
            id=scene_uuid,
            product_id=product_id,
            provider=provider,
            acquisition_at=acquisition_at,
            cloud_coverage_percent=cloud_coverage_percent,
            footprint=footprint,
            crs=crs,
            metadata_json=metadata_json or {},
        )
        self.session.add(scene)
        await self.session.flush()

        # Update native PostGIS geometry column if available
        try:
            async with self.session.begin_nested():
                footprint_json = json.dumps(footprint)
                await self.session.execute(
                    text(
                        "UPDATE scenes SET footprint_geom = ST_SetSRID(ST_GeomFromGeoJSON(:footprint_json), 4326) "
                        "WHERE id = :scene_id"
                    ),
                    {"footprint_json": footprint_json, "scene_id": scene_uuid},
                )
        except Exception:
            pass

        return scene

    async def get_by_id(self, scene_id: uuid.UUID | str) -> Scene | None:
        """Retrieve a scene by its UUID with assets preloaded."""
        if isinstance(scene_id, str):
            try:
                scene_uuid = uuid.UUID(scene_id)
            except ValueError:
                return None
        else:
            scene_uuid = scene_id

        stmt = (
            select(Scene)
            .options(selectinload(Scene.assets), selectinload(Scene.tiles))
            .where(Scene.id == scene_uuid)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_product_id(self, product_id: str) -> Scene | None:
        """Retrieve a scene by its unique provider product ID."""
        stmt = (
            select(Scene)
            .options(selectinload(Scene.assets), selectinload(Scene.tiles))
            .where(Scene.product_id == product_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_scenes(self, limit: int = 100, offset: int = 0) -> list[Scene]:
        """List scenes ordered by acquisition timestamp descending."""
        stmt = (
            select(Scene)
            .options(selectinload(Scene.assets))
            .order_by(Scene.acquisition_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_asset(
        self,
        scene_id: uuid.UUID,
        asset_type: str,
        local_path: str,
        checksum_sha256: str,
        resolution_m: float,
    ) -> SceneAsset:
        """Persist a scene asset (GeoTIFF, reflectance band, mask)."""
        asset = SceneAsset(
            id=uuid.uuid4(),
            scene_id=scene_id,
            asset_type=asset_type,
            local_path=local_path,
            checksum_sha256=checksum_sha256,
            resolution_m=resolution_m,
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def add_tiles(
        self,
        scene_id: uuid.UUID,
        tiles_data: list[dict[str, Any]],
    ) -> list[Tile]:
        """Bulk insert tile records for an ingested scene."""
        tile_entities: list[Tile] = []
        for t in tiles_data:
            tile = Tile(
                id=uuid.uuid4(),
                scene_id=scene_id,
                tile_index=t["tile_index"],
                bounds=t["bounds"],
                local_preview_path=t.get("local_preview_path"),
            )
            self.session.add(tile)
            tile_entities.append(tile)

        await self.session.flush()
        return tile_entities
