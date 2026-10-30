import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from psycopg import sql

from showcase.config import Settings
from showcase.main import create_app
from showcase.migrate import migrate
from showcase.observability import JsonFormatter, logger

from .conftest import TOKEN

pytestmark = pytest.mark.integration


def test_atomic_concurrent_idempotency_and_incident_creation(client, database_url, event, key):
    def submit(_):
        return client.post("/v1/events", json=event, headers={"Idempotency-Key": key})

    with ThreadPoolExecutor(max_workers=12) as executor:
        responses = list(executor.map(submit, range(12)))
    assert sorted(r.status_code for r in responses) == [200] * 11 + [201]
    assert len({r.json()["id"] for r in responses}) == 1
    assert all(r.json() == responses[0].json() for r in responses)
    with psycopg.connect(database_url) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM events WHERE idempotency_key = %s", (key,)
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM incidents WHERE event_id = %s", (responses[0].json()["id"],)
            ).fetchone()[0]
            == 1
        )
    conflict = client.post(
        "/v1/events", json={**event, "component": "ledger"}, headers={"Idempotency-Key": key}
    )
    assert conflict.status_code == 409


def test_concurrent_different_payload_has_one_winner(client, database_url, event, key):
    payloads = [event, {**event, "component": "ledger"}]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda payload: client.post(
                    "/v1/events", json=payload, headers={"Idempotency-Key": key}
                ),
                payloads,
            )
        )
    assert sorted(r.status_code for r in responses) == [201, 409]


def test_normal_events_do_not_create_incidents(client, event, key):
    normal = {**event, "type": "normal", "message": "synthetic check passed"}
    response = client.post("/v1/events", json=normal, headers={"Idempotency-Key": key})
    assert response.status_code == 201
    assert response.json()["incident_id"] is None


def test_resolution_is_repeatable_and_data_survives_app_restart(client, database_url, event, key):
    event_result = client.post("/v1/events", json=event, headers={"Idempotency-Key": key}).json()
    incident_id = event_result["incident_id"]
    result = client.post(f"/v1/incidents/{incident_id}/resolve")
    assert result.status_code == 200
    assert result.json()["status"] == "resolved"
    assert result.json()["resolved_at"] is not None
    assert client.post(f"/v1/incidents/{incident_id}/resolve").json() == result.json()
    assert client.post(f"/v1/incidents/{uuid4()}/resolve").status_code == 404
    assert client.get("/v1/incidents?limit=101").status_code == 422
    assert client.get("/readyz").status_code == 200
    with TestClient(create_app(Settings(database_url, TOKEN))) as restarted:
        restarted.headers.update({"Authorization": f"Bearer {TOKEN}"})
        replay = restarted.post("/v1/events", json=event, headers={"Idempotency-Key": key})
        assert replay.status_code == 200
        assert replay.json() == event_result
        assert result.json() in restarted.get("/v1/incidents?limit=100").json()["items"]


def test_database_failure_rolls_back_event_and_incident(client, database_url, event, key):
    name = "test_fail_" + uuid4().hex
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            sql.SQL("""
            CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF EXISTS (SELECT 1 FROM events WHERE id = NEW.event_id AND idempotency_key = {}) THEN
                RAISE EXCEPTION 'injected synthetic failure';
              END IF;
              RETURN NEW;
            END $$
        """).format(sql.Identifier(name), sql.Literal(key))
        )
        conn.execute(
            sql.SQL(
                "CREATE TRIGGER {} BEFORE INSERT ON incidents FOR EACH ROW EXECUTE FUNCTION {}()"
            ).format(sql.Identifier(name), sql.Identifier(name))
        )
        try:
            response = client.post("/v1/events", json=event, headers={"Idempotency-Key": key})
            assert response.status_code == 503
            assert response.json() == {"detail": "Database unavailable"}
            assert (
                conn.execute(
                    "SELECT count(*) FROM events WHERE idempotency_key = %s", (key,)
                ).fetchone()[0]
                == 0
            )
        finally:
            conn.execute(sql.SQL("DROP TRIGGER {} ON incidents").format(sql.Identifier(name)))
            conn.execute(sql.SQL("DROP FUNCTION {}()").format(sql.Identifier(name)))
    assert (
        client.post("/v1/events", json=event, headers={"Idempotency-Key": key}).status_code == 201
    )


def test_migrations_are_locked_repeatable_and_detect_tampering(database_url, tmp_path):
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(migrate, [database_url] * 4)) == [0] * 4
    (tmp_path / "001_events_and_incidents.sql").write_text("SELECT 1;")
    with pytest.raises(RuntimeError, match="checksum"):
        migrate(database_url, tmp_path)


def test_migration_batch_rolls_back_on_failure(database_url, tmp_path):
    table = "test_atomic_" + uuid4().hex
    (tmp_path / "atomic_001.sql").write_text(f"CREATE TABLE {table} (id integer);")
    (tmp_path / "atomic_002.sql").write_text("SELECT intentional_nonexistent_function();")
    with pytest.raises(psycopg.Error):
        migrate(database_url, tmp_path)
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None
        assert (
            conn.execute(
                "SELECT count(*) FROM schema_migrations WHERE version LIKE 'atomic_%'"
            ).fetchone()[0]
            == 0
        )


def test_bounded_metrics_and_non_superuser_role(client, database_url, event, key):
    created = client.post("/v1/events", json=event, headers={"Idempotency-Key": key}).json()
    for _ in range(3):
        client.post(f"/v1/incidents/{uuid4()}/resolve")
        client.get(f"/unmatched/{uuid4()}")
    metrics = client.get("/metrics").text
    assert "showcase_open_incidents " in metrics
    assert "showcase_database_up 1.0" in metrics
    assert 'route="/v1/incidents/{incident_id}/resolve"' in metrics
    assert 'route="unmatched"' in metrics
    assert created["incident_id"] not in metrics
    with psycopg.connect(database_url) as conn:
        assert conn.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user"
        ).fetchone() == (False, False, False)


def test_native_traces_correlate_json_logs_without_credentials(
    database_url, event, key, monkeypatch
):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("showcase.main.tracer_provider", lambda: provider)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    monkeypatch.setattr(logger, "handlers", [handler])
    with TestClient(create_app(Settings(database_url, TOKEN))) as client:
        response = client.post(
            "/v1/events",
            json=event,
            headers={"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": key},
        )
        assert response.status_code == 201
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "POST /v1/events"
    assert spans[0].attributes["http.response.status_code"] == 201
    log = json.loads(stream.getvalue().strip())
    assert log["event"] == "event_recorded"
    assert log["trace_id"] == f"{spans[0].context.trace_id:032x}"
    assert int(log["trace_id"], 16) != 0
    captured = stream.getvalue() + json.dumps(dict(spans[0].attributes))
    assert TOKEN not in captured
    assert key not in captured
    assert event["message"] not in captured
