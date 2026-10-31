import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from showcase.config import Settings
from showcase.main import EventInput, create_app

TOKEN = "synthetic-unit-token-" + "x" * 32


def test_configuration_requires_explicit_database_and_token(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings.from_env()
    monkeypatch.setenv("DATABASE_URL", "postgresql://app@localhost/showcase")
    with pytest.raises(ValueError, match="API_TOKEN"):
        Settings.from_env()


def test_authentication_and_liveness_do_not_need_database():
    app = create_app(Settings("postgresql://app:unused@127.0.0.1:1/showcase", TOKEN))
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        for token in [None, "wrong", "é" * 32]:
            headers = {} if token is None else {"Authorization": f"Bearer {token}"}
            if token and not token.isascii():
                # HTTP wire headers are latin-1; a valid non-ASCII UTF-8 credential must not crash.
                headers = {b"Authorization": b"Bearer \xc3\xa9"}
            response = client.get("/v1/incidents", headers=headers)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
        assert client.get("/openapi.json").status_code == 401
        schema = client.get("/openapi.json", headers={"Authorization": f"Bearer {TOKEN}"}).json()
        assert "HTTPBearer" in schema["components"]["securitySchemes"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("message", "person@example.com"),
        ("system", "real-bank"),
        ("component", "someone-12345678901"),
        ("type", "transfer"),
    ],
)
def test_only_synthetic_catalog_is_accepted(event, field, value):
    event[field] = value
    with pytest.raises(ValidationError):
        EventInput(**event)


def test_request_body_is_bounded_and_unknown_fields_rejected(event):
    app = create_app(Settings("postgresql://app:unused@127.0.0.1:1/showcase", TOKEN))
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "unit"}
        assert client.post("/v1/events", content=b"x" * 2049, headers=headers).status_code == 413
        assert (
            client.post("/v1/events", content=iter([b"x" * 1024] * 3), headers=headers).status_code
            == 413
        )
        assert (
            client.post(
                "/v1/events", json={**event, "account": "forbidden"}, headers=headers
            ).status_code
            == 422
        )
        for invalid in ["", "' OR 1=1", "x" * 129]:
            assert (
                client.post(
                    "/v1/events",
                    json=event,
                    headers={
                        **headers,
                        "Idempotency-Key": invalid,
                    },
                ).status_code
                == 422
            )
