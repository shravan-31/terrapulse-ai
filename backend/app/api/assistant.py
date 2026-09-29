"""
backend/app/api/assistant.py
Bounded conversational assistant grounded strictly in verified database facts (Phase 11, Master Prompt §11).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.core.settings import settings
from app.repositories.analysis_repository import AnalysisRepository

log = structlog.get_logger("satquery.api.assistant")

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User question or clarification prompt")
    analysis_id: str | None = Field(None, description="Optional Analysis UUID context")


@router.post("/chat")
async def chat_assistant(
    req: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Answers analyst inquiries using strictly grounded database facts.
    Uses Groq LLM if configured; otherwise provides deterministic factual answers.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    context_data: dict[str, Any] = {}

    # 1. Fetch grounded context if analysis_id provided
    if req.analysis_id:
        try:
            ana_uuid = uuid.UUID(req.analysis_id)
            repo = AnalysisRepository(db)
            analysis = await repo.get_by_id(ana_uuid)
            if analysis:
                changes = await repo.list_changes(ana_uuid)
                context_data = {
                    "analysis_id": str(analysis.id),
                    "created_at": analysis.created_at.isoformat(),
                    "changes_count": len(changes),
                    "changes_summary": [
                        {
                            "type": c.change_type,
                            "kind": c.change_kind,
                            "area_m2": c.area_m2,
                            "temporal_status": c.temporal_status,
                            "confidence": c.confidence_score,
                        }
                        for c in changes[:5]
                    ],
                }
        except ValueError:
            pass

    # 2. Query Groq LLM if configured
    if settings.groq_available and settings.groq_api_key:
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.groq_api_key)
            system_prompt = (
                "You are SatQuery AI Assistant. You provide clear, scientific explanations of satellite "
                "imagery analysis. You NEVER fabricate facts. All answers must strictly reflect verified data. "
                "If data is uncalibrated, state it clearly."
            )
            user_content = f"User Question: {req.message}\nVerified Context: {context_data}"
            chat_completion = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                model=settings.groq_model,
                temperature=0.2,
                max_tokens=500,
            )
            reply = chat_completion.choices[0].message.content
            return JSONResponse(
                content={
                    "reply": reply,
                    "engine": "groq",
                    "model": settings.groq_model,
                    "grounded_context": bool(context_data),
                    "request_id": request_id,
                }
            )
        except Exception as exc:
            log.warning("Groq call failed, falling back to deterministic factual response", error=str(exc))

    # 3. Deterministic factual fallback (Groq unavailable / disabled)
    if context_data:
        cnt = context_data.get("changes_count", 0)
        reply = (
            f"Based on verified database records for analysis {req.analysis_id}: "
            f"{cnt} candidate change polygon(s) were detected using bi-temporal comparison. "
            "Confidence scores are uncalibrated per system guidelines. Review polygons on the map for confirmation."
        )
    else:
        reply = (
            "SatQuery AI provides semantic satellite search, multi-temporal change detection, and "
            "audit provenance. To analyze a specific event, select an AOI and trigger change analysis."
        )

    return JSONResponse(
        content={
            "reply": reply,
            "engine": "deterministic_fallback",
            "model": "rule_based_grounded",
            "grounded_context": bool(context_data),
            "request_id": request_id,
        }
    )
