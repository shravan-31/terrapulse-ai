"""
backend/app/repositories/analysis_repository.py
SQLAlchemy / PostGIS persistence repository for Analyses, Changes, and Analyst Decisions.

Implements ADR-006, ADR-007, ADR-013:
- Canonical change taxonomy enforcement.
- Native PostGIS geometry synchronization for change polygons.
- Full audit history of analyst review decisions.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import Analysis, AnalystDecision, Change


class AnalysisRepository:
    """Handles database persistence for Analysis, Change, and AnalystDecision entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_analysis(
        self,
        aoi_id: uuid.UUID,
        title: str = "Bi-Temporal Change Analysis",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        status: str = "running",
        analysis_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> Analysis:
        """Create and persist an Analysis entity."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        resolved_title = title or kwargs.get("analysis_type", "Bi-Temporal Change Analysis")
        analysis = Analysis(
            id=analysis_id or uuid.uuid4(),
            aoi_id=aoi_id,
            title=resolved_title,
            status=status,
            start_time=start_time or now,
            end_time=end_time or now,
        )
        if "baseline_scene_id" in kwargs:
            analysis.baseline_scene_id = kwargs["baseline_scene_id"]
        if "comparison_scene_id" in kwargs:
            analysis.comparison_scene_id = kwargs["comparison_scene_id"]
        if "parameters" in kwargs:
            analysis.parameters = kwargs["parameters"]
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def get_by_id(self, analysis_id: uuid.UUID | str) -> Analysis | None:
        """Alias for get_analysis."""
        return await self.get_analysis(analysis_id)

    async def get_analysis(self, analysis_id: uuid.UUID | str) -> Analysis | None:
        """Retrieve an Analysis by UUID with changes preloaded."""
        if isinstance(analysis_id, str):
            try:
                analysis_uuid = uuid.UUID(analysis_id)
            except ValueError:
                return None
        else:
            analysis_uuid = analysis_id

        stmt = (
            select(Analysis)
            .options(selectinload(Analysis.changes))
            .where(Analysis.id == analysis_uuid)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_analyses(
        self,
        aoi_id: uuid.UUID | str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Analysis]:
        """List analyses ordered by creation timestamp descending."""
        stmt = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit).offset(offset)
        if aoi_id:
            aoi_uuid = uuid.UUID(aoi_id) if isinstance(aoi_id, str) else aoi_id
            stmt = stmt.where(Analysis.aoi_id == aoi_uuid)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_change(
        self,
        analysis_id: uuid.UUID,
        change_type: str,
        change_kind: str,
        temporal_status: str,
        earliest_supported_at: datetime,
        latest_observation_at: datetime,
        polygon: dict[str, Any],
        area_m2: float,
        pixel_count: int,
        confidence_score: float = 0.0,
        confidence_details: dict[str, Any] | None = None,
        last_baseline_observation_at: datetime | None = None,
        confirmed_at: datetime | None = None,
        change_id: uuid.UUID | None = None,
    ) -> Change:
        """Create and persist a detected Change record."""
        change_uuid = change_id or uuid.uuid4()
        change = Change(
            id=change_uuid,
            analysis_id=analysis_id,
            change_type=change_type,
            change_kind=change_kind,
            temporal_status=temporal_status,
            earliest_supported_at=earliest_supported_at,
            latest_observation_at=latest_observation_at,
            last_baseline_observation_at=last_baseline_observation_at,
            confirmed_at=confirmed_at,
            polygon=polygon,
            area_m2=area_m2,
            pixel_count=pixel_count,
            confidence_score=confidence_score,
            confidence_details=confidence_details or {},
        )
        self.session.add(change)
        await self.session.flush()
        return change

    async def list_changes(
        self,
        analysis_id: uuid.UUID | str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Change]:
        """List detected changes for an analysis."""
        analysis_uuid = uuid.UUID(analysis_id) if isinstance(analysis_id, str) else analysis_id
        stmt = (
            select(Change)
            .options(selectinload(Change.decisions))
            .where(Change.analysis_id == analysis_uuid)
            .order_by(Change.confidence_score.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_analyst_decision(
        self,
        change_id: uuid.UUID | str,
        operator: str,
        review_status: str,
        notes: str | None = None,
    ) -> AnalystDecision:
        """Persist an analyst decision review for a detected change."""
        change_uuid = uuid.UUID(change_id) if isinstance(change_id, str) else change_id
        decision = AnalystDecision(
            id=uuid.uuid4(),
            change_id=change_uuid,
            operator=operator,
            review_status=review_status,
            notes=notes,
        )
        self.session.add(decision)
        await self.session.flush()
        return decision

    async def get_analyst_decisions(
        self,
        change_id: uuid.UUID | str,
    ) -> list[AnalystDecision]:
        """Retrieve review decisions for a specific change."""
        change_uuid = uuid.UUID(change_id) if isinstance(change_id, str) else change_id
        stmt = (
            select(AnalystDecision)
            .where(AnalystDecision.change_id == change_uuid)
            .order_by(AnalystDecision.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
