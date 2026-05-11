"""Shared pytest fixtures for FastenerGPT backend tests."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Override settings before importing app.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
