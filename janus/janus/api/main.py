"""FastAPI app factory.

Used by the runner (`scripts/run_api.py`) and by tests. The factory pattern
lets tests build a fresh app per-test (no shared state surprises).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from janus import __version__
from janus.api.middleware import attach_middlewares, limiter
from janus.api.routes import admin, health, journal, portfolio, regime, strategies
from janus.config.settings import Settings, get_settings
from janus.monitoring.logging_config import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Janus Trading API",
        description="Multi-strategy crypto trading system control plane.",
        version=__version__,
        default_response_class=ORJSONResponse,
        docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json",
    )
    attach_middlewares(app)

    # Apply default rate limit on every router (default: 120/min, peer-keyed).
    @app.on_event("startup")
    async def _set_default_limits() -> None:  # pragma: no cover - thin glue
        limiter._default_limits = [f"{settings.api.rate_limit_per_minute}/minute"]

    # Routers
    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(strategies.router)
    app.include_router(journal.router)
    app.include_router(regime.router)
    app.include_router(admin.router)

    return app


# Default app instance used by uvicorn:
#   uvicorn janus.api.main:app --host 0.0.0.0 --port $PORT
app = create_app()
