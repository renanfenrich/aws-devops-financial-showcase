import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Annotated, Literal
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from psycopg.types.json import Jsonb
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict

from showcase.config import Settings
from showcase.db import create_pool
from showcase.observability import logger, tracer_provider


class EventInput(BaseModel):
    """Only the synthetic catalog is accepted; free text/PII is never persisted."""

    model_config = ConfigDict(extra="forbid", strict=True)
    system: Literal["synthetic-finance"]
    component: Literal["payments", "ledger", "settlement"]
    type: Literal["normal", "failure"]
    message: Literal["synthetic check passed", "synthetic check failed"]


class EventOutput(EventInput):
    id: UUID
    created_at: datetime
    incident_id: UUID | None


class Incident(BaseModel):
    id: UUID
    event_id: UUID
    system: str
    component: str
    status: Literal["open", "resolved"]
    opened_at: datetime
    resolved_at: datetime | None


class IncidentList(BaseModel):
    items: list[Incident]


class BodyLimitMiddleware:
    """Bound JSON intake even with chunked transfer encoding."""

    def __init__(self, app, limit: int = 2048):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.limit:
                return await JSONResponse({"detail": "Request body too large"}, 413)(
                    scope, receive, send
                )
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        pending = True

        async def bounded_receive():
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    pool = create_pool(config.database_url)
    provider = tracer_provider()
    registry = CollectorRegistry()
    requests = Counter(
        "showcase_http_requests",
        "Completed requests",
        ["method", "route", "status"],
        registry=registry,
    )
    duration = Histogram(
        "showcase_http_request_duration_seconds",
        "Request latency",
        ["method", "route"],
        registry=registry,
    )
    open_incidents = Gauge("showcase_open_incidents", "Persisted open incidents", registry=registry)
    database_up = Gauge("showcase_database_up", "Database is reachable", registry=registry)

    @asynccontextmanager
    async def lifespan(app):
        pool.open()
        try:
            yield
        finally:
            pool.close()
            provider.shutdown()

    app = FastAPI(
        title="Synthetic Financial Operations API",
        version="0.1.0",
        description="Local showcase using synthetic events only; no real financial operations.",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        telemetry={
            "tracer_provider": provider,
            "logs": False,
            "metrics": False,
            "operation_spans": False,
            "auto_configure": False,
            "exclude": lambda scope: scope.get("path") in {"/healthz", "/readyz", "/metrics"},
        },
    )
    app.state.pool = pool
    bearer = HTTPBearer(auto_error=False)

    def require_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        if not credentials or not secrets.compare_digest(
            credentials.credentials.encode(), config.api_token.encode()
        ):
            raise HTTPException(
                401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
            )

    protected = [Depends(require_token)]
    app.add_middleware(BodyLimitMiddleware)

    @app.middleware("http")
    async def request_metrics(request: Request, call_next):
        start = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            method = (
                request.method if request.method in {"GET", "POST", "HEAD", "OPTIONS"} else "OTHER"
            )
            if route != "/metrics":
                requests.labels(method, route, str(status)).inc()
                duration.labels(method, route).observe(perf_counter() - start)

    @app.exception_handler(psycopg.Error)
    @app.exception_handler(PoolTimeout)
    async def database_error(_request, _exc):
        logger.warning("database_unavailable")
        return JSONResponse({"detail": "Database unavailable"}, 503)

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        try:
            with pool.connection() as conn:
                row = conn.execute(
                    "SELECT to_regclass('public.events') IS NOT NULL "
                    "AND to_regclass('public.incidents') IS NOT NULL AS ready"
                ).fetchone()
            if not row["ready"]:
                return JSONResponse({"status": "not_ready"}, 503)
        except psycopg.Error, PoolTimeout:
            return JSONResponse({"status": "not_ready"}, 503)
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        try:
            with pool.connection() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) AS total FROM incidents WHERE status = 'open'"
                ).fetchone()["total"]
            database_up.set(1)
            open_incidents.set(count)
        except psycopg.Error, PoolTimeout:
            database_up.set(0)
            open_incidents.set(float("nan"))
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    @app.get("/openapi.json", dependencies=protected, include_in_schema=False)
    def openapi():
        return JSONResponse(app.openapi())

    @app.post("/v1/events", response_model=EventOutput, status_code=201, dependencies=protected)
    def record_event(
        event: EventInput,
        response: Response,
        idempotency_key: Annotated[
            str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
        ],
    ):
        payload = event.model_dump()
        incident_id = None
        with pool.connection() as conn:
            created = conn.execute(
                "INSERT INTO events (id, idempotency_key, payload) VALUES (%s, %s, %s) "
                "ON CONFLICT (idempotency_key) DO NOTHING RETURNING id, created_at",
                (uuid4(), idempotency_key, Jsonb(payload)),
            ).fetchone()
            if created:
                if event.type == "failure":
                    incident_id = uuid4()
                    conn.execute(
                        "INSERT INTO incidents (id, event_id, system, component) "
                        "VALUES (%s, %s, %s, %s)",
                        (incident_id, created["id"], event.system, event.component),
                    )
                result = {**payload, **created, "incident_id": incident_id}
            else:
                existing = conn.execute(
                    "SELECT e.id, e.created_at, e.payload, i.id AS incident_id FROM events e "
                    "LEFT JOIN incidents i ON i.event_id = e.id WHERE e.idempotency_key = %s",
                    (idempotency_key,),
                ).fetchone()
                if existing["payload"] != payload:
                    raise HTTPException(409, "Idempotency key already used for a different event")
                result = {**existing.pop("payload"), **existing}
                response.status_code = 200
                response.headers["Idempotency-Replayed"] = "true"
        logger.info("event_recorded" if created else "event_replayed")
        return result

    @app.get("/v1/incidents", response_model=IncidentList, dependencies=protected)
    def list_incidents(limit: Annotated[int, Query(ge=1, le=100)] = 50):
        with pool.connection() as conn:
            items = conn.execute(
                "SELECT * FROM incidents ORDER BY opened_at DESC, id DESC LIMIT %s", (limit,)
            ).fetchall()
        return {"items": items}

    @app.post(
        "/v1/incidents/{incident_id}/resolve", response_model=Incident, dependencies=protected
    )
    def resolve_incident(incident_id: UUID):
        with pool.connection() as conn:
            incident = conn.execute(
                "UPDATE incidents SET status = 'resolved', "
                "resolved_at = COALESCE(resolved_at, CURRENT_TIMESTAMP) WHERE id = %s RETURNING *",
                (incident_id,),
            ).fetchone()
            if not incident:
                raise HTTPException(404, "Incident not found")
        logger.info("incident_resolved")
        return incident

    return app
