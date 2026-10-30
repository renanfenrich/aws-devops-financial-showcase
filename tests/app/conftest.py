import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from showcase.config import Settings
from showcase.main import create_app
from showcase.migrate import migrate

TOKEN = "synthetic-test-token-" + "x" * 32


@pytest.fixture(scope="session")
def database_url():
    dsn = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("integration requires TEST_DATABASE_URL or DATABASE_URL; run make test")
    migrate(dsn)
    return dsn


@pytest.fixture
def client(database_url):
    app = create_app(Settings(database_url, TOKEN))
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {TOKEN}"})
        yield client


@pytest.fixture
def event():
    return {
        "system": "synthetic-finance",
        "component": "payments",
        "type": "failure",
        "message": "synthetic check failed",
    }


@pytest.fixture
def key():
    return "test-" + str(uuid4())
