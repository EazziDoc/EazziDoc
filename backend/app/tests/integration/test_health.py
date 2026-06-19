"""Integration tests for the health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_response_structure(client: AsyncClient):
    resp = await client.get("/health")
    data = resp.json()

    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "environment" in data
    assert "checks" in data
    assert "db" in data["checks"]


@pytest.mark.asyncio
async def test_health_db_check_passes(client: AsyncClient):
    """DB must be reachable in the test environment."""
    resp = await client.get("/health")
    assert resp.json()["checks"]["db"] == "ok"
    assert resp.json()["status"] == "ok"
