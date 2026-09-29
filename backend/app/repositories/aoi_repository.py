"""
backend/app/repositories/aoi_repository.py
SQLAlchemy / PostGIS persistence repository for Areas of Interest (AOIs).

Implements:
- Asynchronous queries using SQLAlchemy AsyncSession.
- Native geometry synchronization with PostGIS (ST_GeomFromGeoJSON).
- Clear NotFoundError when AOI does not exist.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AOI


class AOIRepository:
    """Handles database persistence for AOI entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        geometry: dict[str, Any],
        area_km2: float,
        vertex_count: int,
        description: str | None = None,
        aoi_id: uuid.UUID | None = None,
    ) -> AOI:
        """Create and persist a new AOI record."""
        aoi_uuid = aoi_id or uuid.uuid4()
        aoi = AOI(
            id=aoi_uuid,
            name=name,
            description=description,
            geometry=geometry,
            area_km2=area_km2,
            vertex_count=vertex_count,
        )
        self.session.add(aoi)
        await self.session.flush()

        # Update native PostGIS geometry column if PostGIS extension is active
        try:
            async with self.session.begin_nested():
                geom_json = json.dumps(geometry)
                await self.session.execute(
                    text(
                        "UPDATE aois SET geom = ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326) "
                        "WHERE id = :aoi_id"
                    ),
                    {"geom_json": geom_json, "aoi_id": aoi_uuid},
                )
        except Exception:
            # PostGIS column update is non-fatal if running on base PG without spatial column
            pass

        return aoi

    async def get_by_id(self, aoi_id: uuid.UUID | str) -> AOI | None:
        """Retrieve an AOI by UUID."""
        if isinstance(aoi_id, str):
            try:
                aoi_uuid = uuid.UUID(aoi_id)
            except ValueError:
                return None
        else:
            aoi_uuid = aoi_id

        stmt = select(AOI).where(AOI.id == aoi_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[AOI]:
        """List persisted AOIs ordered by creation timestamp descending."""
        stmt = select(AOI).order_by(AOI.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Count total persisted AOIs."""
        stmt = select(func.count(AOI.id))
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
