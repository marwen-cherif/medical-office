import pytest
from httpx import ASGITransport, AsyncClient

from crm.db import app_dir, connect
from crm.server import STATE, app


@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": "Bearer testtoken"}
        response = await client.get("/api/health", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "schema_version" in data


@pytest.mark.asyncio
async def test_db_isolation(test_db):
    cursor = test_db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='patients'"
    )
    assert cursor.fetchone() is not None
