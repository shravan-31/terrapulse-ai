"""
backend/app/api/provenance.py
Immutable audit log and provenance chain API endpoints (Phase 10, ADR-002, ADR-015).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationError
from app.models.entities import Provenance
from app.repositories.provenance_repository import ProvenanceRepository

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


@router.get("/{entity_id}")
async def get_provenance_chain(
    entity_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Retrieve the immutable lineage and audit chain for a specific entity
    (scene, tile, analysis, change, or decision).
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    try:
        e_uuid = uuid.UUID(entity_id)
    except ValueError:
        raise ValidationError(detail=f"Invalid entity UUID: {entity_id}")

    repo = ProvenanceRepository(db)
    records = await repo.get_history(entity_id=e_uuid)

    if not records:
        # Check if record exists directly in provenance by entity_id
        stmt = select(Provenance).where(Provenance.entity_id == e_uuid).order_by(Provenance.created_at.asc())
        res = await db.execute(stmt)
        records = list(res.scalars().all())

    return JSONResponse(
        content={
            "entity_id": entity_id,
            "chain_length": len(records),
            "records": [
                {
                    "id": str(r.id),
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "operator_username": r.operator_username,
                    "parameters": r.parameters,
                    "created_at": r.created_at.isoformat(),
                }
                for r in records
            ],
            "request_id": request_id,
        }
    )


@router.get("")
async def list_recent_provenance(
    limit: int = Query(50, ge=1, le=100),
    action: str | None = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """List recent provenance actions across the platform."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())
    stmt = select(Provenance).order_by(Provenance.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(Provenance.action == action)

    res = await db.execute(stmt)
    records = list(res.scalars().all())

    return JSONResponse(
        content={
            "count": len(records),
            "records": [
                {
                    "id": str(r.id),
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "entity_id": str(r.entity_id),
                    "operator_username": r.operator_username,
                    "parameters": r.parameters,
                    "created_at": r.created_at.isoformat(),
                }
                for r in records
            ],
            "request_id": request_id,
        }
    )
