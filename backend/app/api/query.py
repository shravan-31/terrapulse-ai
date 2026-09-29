"""
backend/app/api/query.py
Natural language query parsing endpoint for SatQuery AI.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.services.query_parser import QueryParseResponse, parse_natural_language_query

router = APIRouter(prefix="/api/query", tags=["query"])


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language satellite search prompt")


@router.post("/parse", response_model=QueryParseResponse)
async def parse_query(req: QueryRequest):
    """
    Parses a natural language satellite search query into structured search filters.
    Uses Groq LLM if available, with deterministic fallback.
    """
    return await parse_natural_language_query(req.query)
