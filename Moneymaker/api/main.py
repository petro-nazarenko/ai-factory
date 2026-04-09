"""FastAPI control plane — HTTP API + Prometheus metrics endpoint.

Endpoints
---------
POST /cycles/start          — fire a full pipeline run
GET  /cycles/{id}           — poll task status
POST /conversions           — record conversion event (Stripe webhook, pixel, etc.)
GET  /weights               — current feature weights from learning agent
GET  /ideas                 — recent ideas with filter outcomes
GET  /metrics               — Prometheus scrape endpoint
GET  /healthz               — liveness probe
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

import core.metrics  # noqa: F401 — registers all counters on import
from api.routes import router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Moneymaker Control Plane",
    description="Autonomous revenue-seeking swarm — control API",
    version="5.0.0",
)

app.include_router(router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# Per-request HTTP metrics (local to this module)
# ---------------------------------------------------------------------------

_http_requests = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
_http_latency = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    path = request.url.path
    _http_requests.labels(request.method, path, response.status_code).inc()
    _http_latency.labels(request.method, path).observe(duration)
    return response


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    from infra.db import create_tables
    await create_tables()
    logging.getLogger(__name__).info("Moneymaker control plane ready.")
