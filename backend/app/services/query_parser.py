"""
backend/app/services/query_parser.py
Natural language query parser service for SatQuery AI.
Implements ADR-015 and Master Prompt §§11-12.

Rules:
1. When Groq is available and configured, calls Groq with structured prompt and strict schema.
2. When Groq is absent, fails, times out, or produces invalid JSON, falls back to deterministic rule-based parsing.
3. Always returns structured ParsedQuery with `used_fallback: bool` and actionable filters.
4. Never produces raw SQL or executes commands.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.core.settings import settings


class ParsedFilters(BaseModel):
    semantic_prompt: str = Field(..., description="Target text prompt for RemoteCLIP embedding search")
    start_date: str | None = Field(None, description="ISO format start date YYYY-MM-DD")
    end_date: str | None = Field(None, description="ISO format end date YYYY-MM-DD")
    max_cloud_cover: float = Field(20.0, ge=0.0, le=100.0, description="Max cloud cover percent")
    change_type: str | None = Field(None, description="construction | clearance | water_variation | etc.")
    change_kind: str | None = Field(None, description="appearance | disappearance | expansion | contraction")
    location_keyword: str | None = Field(None, description="Identified place name or region")


class QueryParseResponse(BaseModel):
    query: str
    parsed: ParsedFilters
    used_fallback: bool
    parser_model: str
    notice: str | None = None


def deterministic_fallback_parse(query: str) -> ParsedFilters:
    """
    Robust rule-based parser when LLM is unavailable or fails.
    Extracts dates, cloud thresholds, change keywords, and cleans semantic prompt.
    """
    q_lower = query.lower()
    
    # 1. Cloud cover extraction (e.g., "cloud < 10%", "under 15% cloud", "10% cloud")
    cloud_match = re.search(r"(\d{1,2})\s*%\s*cloud", q_lower) or re.search(r"cloud\s*(?:under|<|less than)?\s*(\d{1,2})", q_lower)
    max_cloud = float(cloud_match.group(1)) if cloud_match else 20.0

    # 2. Year / Date extraction (e.g., "2023 to 2024", "between 2022 and 2023", "in 2024")
    year_range = re.findall(r"\b(201[5-9]|202[0-6])\b", q_lower)
    start_date = None
    end_date = None
    if len(year_range) >= 2:
        start_date = f"{min(year_range)}-01-01"
        end_date = f"{max(year_range)}-12-31"
    elif len(year_range) == 1:
        start_date = f"{year_range[0]}-01-01"
        end_date = f"{year_range[0]}-12-31"

    # 3. Change taxonomy keywords
    change_type = None
    if any(k in q_lower for k in ["build", "construction", "infrastructure", "structure"]):
        change_type = "construction"
    elif any(k in q_lower for k in ["clear", "clearance", "deforest", "logging", "cleared"]):
        change_type = "clearance"
    elif any(k in q_lower for k in ["water", "flood", "lake", "reservoir", "river"]):
        change_type = "water_variation"
    elif any(k in q_lower for k in ["vegetation", "crop", "forest", "greening"]):
        change_type = "vegetation_land_cover"
    elif any(k in q_lower for k in ["road", "highway", "pavement"]):
        change_type = "road_development"

    change_kind = None
    if any(k in q_lower for k in ["new", "appearance", "built", "appeared"]):
        change_kind = "appearance"
    elif any(k in q_lower for k in ["demolished", "removed", "disappeared", "disappearance"]):
        change_kind = "disappearance"
    elif any(k in q_lower for k in ["expanded", "expansion", "growth"]):
        change_kind = "expansion"
    elif any(k in q_lower for k in ["shrink", "shrinking", "contraction"]):
        change_kind = "contraction"

    # 4. Clean semantic prompt (strip temporal and noise words)
    cleaned_prompt = re.sub(r"\b(in|from|to|between|and|under|less than|\d{1,2}%|cloud|clouds|\d{4})\b", "", query, flags=re.IGNORECASE)
    cleaned_prompt = " ".join(cleaned_prompt.split()).strip()
    if not cleaned_prompt:
        cleaned_prompt = query

    return ParsedFilters(
        semantic_prompt=cleaned_prompt,
        start_date=start_date,
        end_date=end_date,
        max_cloud_cover=max_cloud,
        change_type=change_type,
        change_kind=change_kind,
    )


async def parse_natural_language_query(query: str) -> QueryParseResponse:
    """
    Main parser entrypoint. Attempts Groq if configured, falls back deterministically.
    """
    if not settings.groq_available:
        return QueryParseResponse(
            query=query,
            parsed=deterministic_fallback_parse(query),
            used_fallback=True,
            parser_model="deterministic-fallback-v1",
            notice="Groq API key not configured; parsed using deterministic rules.",
        )

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)

        system_prompt = (
            "You are an expert satellite imagery query parser. Output ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "semantic_prompt": "compact visual description for RemoteCLIP text embedding search",\n'
            '  "start_date": "YYYY-MM-DD or null",\n'
            '  "end_date": "YYYY-MM-DD or null",\n'
            '  "max_cloud_cover": number between 0 and 100,\n'
            '  "change_type": "construction" | "clearance" | "water_variation" | "vegetation_land_cover" | "road_development" | null,\n'
            '  "change_kind": "appearance" | "disappearance" | "expansion" | "contraction" | null,\n'
            '  "location_keyword": "extracted place name or null"\n'
            "}\n"
            "Do not output markdown codeblocks, explanations, or any other text."
        )

        resp = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        raw_text = resp.choices[0].message.content or "{}"
        data = json.loads(raw_text)
        parsed = ParsedFilters.model_validate(data)

        return QueryParseResponse(
            query=query,
            parsed=parsed,
            used_fallback=False,
            parser_model=settings.groq_model,
        )
    except Exception as e:
        # Graceful fallback on timeout, parse error, or Groq API failure
        return QueryParseResponse(
            query=query,
            parsed=deterministic_fallback_parse(query),
            used_fallback=True,
            parser_model="deterministic-fallback-v1",
            notice=f"LLM parser error ({e.__class__.__name__}); fell back to deterministic rules.",
        )
