"""Public API surface for the v2 Gong reasoning flow."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_surface_keeps_upload_and_v2_gong_flow_only(client: AsyncClient) -> None:
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/api/v1/drawings/upload" in paths
    assert "/api/v1/drawings/{drawing_id}/understand" in paths
    assert "/api/v1/designs/v2/generate" in paths
    assert "/api/v1/designs/v2/{design_id}/parameters" in paths
    assert "/api/v1/designs/v2/{design_id}/reasoning" in paths

    assert "/api/v1/designs/generate" not in paths
    assert "/api/v1/rag/stats" not in paths
    assert "/api/v1/geometry/preview" not in paths
    assert "/api/v1/designs/v2/{design_id}/dxf" not in paths
    assert "/api/v1/designs/v2/{design_id}/preview" not in paths
