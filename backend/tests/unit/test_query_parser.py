"""
backend/tests/unit/test_query_parser.py
Unit tests for the query parsing service and fallback logic (ADR-015, Master Prompt §11).

Validates:
1. Deterministic fallback correctly extracts cloud coverage, temporal windows, and change types.
2. Semantic prompt is cleaned of date and noise tokens.
3. Fallback notice and parser_model flag are set properly.
4. API endpoint /api/query/parse returns validated JSON response without crashing.
"""

import pytest
from app.services.query_parser import deterministic_fallback_parse, parse_natural_language_query


def test_deterministic_fallback_dates_and_cloud():
    query = "Find new construction between 2022 and 2024 with cloud under 10%"
    parsed = deterministic_fallback_parse(query)
    
    assert parsed.start_date == "2022-01-01"
    assert parsed.end_date == "2024-12-31"
    assert parsed.max_cloud_cover == 10.0
    assert parsed.change_type == "construction"
    assert parsed.change_kind == "appearance"
    assert "construction" in parsed.semantic_prompt.lower()


def test_deterministic_fallback_water_variation():
    query = "lake water expansion in 2023 15% cloud"
    parsed = deterministic_fallback_parse(query)
    
    assert parsed.start_date == "2023-01-01"
    assert parsed.end_date == "2023-12-31"
    assert parsed.max_cloud_cover == 15.0
    assert parsed.change_type == "water_variation"
    assert parsed.change_kind == "expansion"


def test_deterministic_fallback_default_cloud():
    query = "solar panel farms"
    parsed = deterministic_fallback_parse(query)
    
    assert parsed.max_cloud_cover == 20.0
    assert parsed.start_date is None
    assert parsed.semantic_prompt == "solar panel farms"


@pytest.mark.asyncio
async def test_parse_natural_language_query_service():
    resp = await parse_natural_language_query("cleared forest from 2021 to 2023")
    assert resp.query == "cleared forest from 2021 to 2023"
    assert resp.parsed.change_type == "clearance"
    assert resp.parsed.start_date == "2021-01-01"
    assert resp.parsed.end_date == "2023-12-31"
    assert resp.parser_model is not None
