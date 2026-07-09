import pytest
from httpx import ASGITransport, AsyncClient

from crm.db import app_dir, connect
from crm.server import STATE, app


@pytest.fixture(scope="session", autouse=True)
def configure_token():
    STATE.token = "testtoken"
    yield


@pytest.fixture(autouse=True)
def test_db():
    test_db_path = app_dir() / "data" / "cabinet_test.db"

    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except OSError:
            pass

    # Connect to the test db (runs schema and migrations)
    conn = connect(test_db_path)

    old_conn = STATE.conn
    STATE.conn = conn

    yield conn

    conn.close()
    STATE.conn = old_conn

    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except OSError:
            pass


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
