"""Tests for the health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_schema(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_environment_is_test(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    data = response.json()
    assert data["environment"] == "test"
