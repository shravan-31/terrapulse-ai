"""
backend/app/repositories/provenance_repository.py
SQLAlchemy persistence repository for Provenance audit trails (ADR-002, ADR-015).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Provenance


class ProvenanceRepository:
    """Handles database persistence for immutable scientific provenance records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        artifact_id: str,
        artifact_type: str,
        parent_artifact_ids: list[str] | None = None,
        source_references: list[str] | None = None,
        model_name: str | None = None,
        model_sha256: str | None = None,
        code_version: str = "0.1.0",
        parameters: dict[str, Any] | None = None,
    ) -> Provenance:
        """Create and persist an immutable provenance record."""
        record = Provenance(
            id=uuid.uuid4(),
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            parent_artifact_ids=parent_artifact_ids or [],
            source_references=source_references or [],
            model_name=model_name,
            model_sha256=model_sha256,
            code_version=code_version,
            parameters=parameters or {},
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: Any,
        operator_username: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Provenance:
        """Convenience method to log an action as an immutable provenance record."""
        return await self.record(
            artifact_id=str(entity_id),
            artifact_type=entity_type,
            source_references=[f"operator:{operator_username}"] if operator_username else [],
            parameters={"action": action, **(parameters or {})},
        )

    async def get_by_artifact_id(self, artifact_id: str) -> list[Provenance]:
        """Retrieve all provenance records associated with an artifact."""
        stmt = (
            select(Provenance)
            .where(Provenance.artifact_id == artifact_id)
            .order_by(Provenance.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
