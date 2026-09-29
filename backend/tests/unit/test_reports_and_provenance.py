"""
backend/tests/unit/test_reports_and_provenance.py
Unit tests for Provenance chains, Grounded Assistant, and Multi-format Report Exports (Phase 10, Phase 11).
"""

from __future__ import annotations

import base64
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.reports import _sanitize_csv_cell
from app.core.settings import settings
from app.main import create_app


def _auth_headers() -> dict[str, str]:
    encoded = base64.b64encode(
        f"{settings.operator_username}:{settings.operator_password}".encode()
    ).decode()
    return {"Authorization": f"Basic {encoded}"}


def test_csv_formula_injection_sanitization():
    """Verify ADR-014 CSV formula injection prevention: '=', '+', '-', '@' escaped."""
    assert _sanitize_csv_cell("normal_text") == "normal_text"
    assert _sanitize_csv_cell("=1+1") == "'=1+1"
    assert _sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert _sanitize_csv_cell("-2+3") == "'-2+3"
    assert _sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"


@pytest.mark.asyncio
async def test_provenance_list_endpoint():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/provenance", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert "count" in data


@pytest.mark.asyncio
async def test_assistant_chat_deterministic_fallback():
    app = create_app()
    payload = {
        "message": "Explain what changes were detected in the agricultural area",
        "analysis_id": None,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/assistant/chat", json=payload, headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert data["engine"] in ("groq", "deterministic_fallback")


@pytest.mark.asyncio
async def test_report_invalid_analysis_uuid():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/report/generate",
            json={"analysis_id": "invalid-uuid", "format": "json"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "Invalid analysis UUID" in data.get("error", "")
