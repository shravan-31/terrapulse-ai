"""
backend/app/services/review_service.py
Analyst review and human-in-the-loop audit workflow service (Section 7).

Implements:
- Recording analyst decisions: CONFIRM, REJECT, NEEDS REVIEW
- Notes, corrected change type, and confidence override
- Permanent database audit logging
- Full provenance traceability
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AnalystDecision, Change
from app.repositories.analysis_repository import AnalysisRepository

log = structlog.get_logger("satquery.services.review")


async def submit_review(
    session: AsyncSession,
    change_id: uuid.UUID,
    status: str,  # "CONFIRM", "REJECT", "NEEDS_REVIEW", or canonical "confirmed_by_analyst"
    operator_name: str = "operator",
    notes: Optional[str] = None,
    corrected_type: Optional[str] = None,
    confidence_override: Optional[float] = None,
) -> dict[str, Any]:
    """
    Record an analyst verification decision permanently in PostgreSQL.
    """
    # Map to canonical database status
    status_map = {
        "CONFIRM": "confirmed_by_analyst",
        "REJECT": "rejected_by_analyst",
        "NEEDS_REVIEW": "flagged",
        "NEEDS REVIEW": "flagged",
        "confirmed_by_analyst": "confirmed_by_analyst",
        "rejected_by_analyst": "rejected_by_analyst",
        "flagged": "flagged",
    }
    canonical_status = status_map.get(status.upper(), "flagged")

    repo = AnalysisRepository(session)

    # If corrected type or confidence override is provided, update change record
    if corrected_type or confidence_override is not None:
        change = await session.get(Change, change_id)
        if change:
            if corrected_type:
                change.change_type = corrected_type
            if confidence_override is not None:
                change.confidence_score = float(confidence_override)
            await session.commit()

    decision = await repo.record_decision(
        change_id=change_id,
        analyst_username=operator_name,
        decision=canonical_status,
        notes=notes,
    )

    log.info(
        "Analyst review decision recorded",
        change_id=str(change_id),
        decision=canonical_status,
        operator=operator_name,
    )

    return {
        "review_id": str(decision.id),
        "change_id": str(change_id),
        "status": canonical_status,
        "operator": operator_name,
        "notes": notes,
        "corrected_type": corrected_type,
        "confidence_override": confidence_override,
        "created_at": decision.created_at.isoformat(),
    }
