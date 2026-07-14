import pytest
from crm.db import app_dir, connect
from crm.server import STATE


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
