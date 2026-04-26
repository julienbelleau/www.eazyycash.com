"""Request middleware: structured logging + per-key rate limiting + request IDs."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from loguru import logger
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from janus.config.settings import get_settings


def _key_func(request: Request) -> str:
    """Identify the caller for rate limiting.

    Priority: API key short id (header parsed) > client IP. We don't import
    the auth resolver here to avoid a circular dep; we eyeball the header.
    """
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and "_" in auth:
        body = auth[7:]
        if body.startswith("jns_"):
            short_chunk = body.split("_", 2)
            if len(short_chunk) >= 2:
                return f"key:{short_chunk[1]}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key_func, default_limits=[])


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inject a request id + log timing for every request."""

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        rid_hdr = settings.api.request_id_header
        request_id = request.headers.get(rid_hdr) or str(uuid.uuid4())
        log = logger.bind(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            client=get_remote_address(request),
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            log.exception("request failed: {}", exc)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response.headers[rid_hdr] = request_id
        log.bind(status=response.status_code, elapsed_ms=round(elapsed_ms, 2)).info("request")
        return response


def attach_middlewares(app: FastAPI) -> None:
    """Wire middlewares + rate limiter onto a FastAPI instance."""
    settings = get_settings()
    # CORS
    from fastapi.middleware.cors import CORSMiddleware
    origins = [
        o.strip() for o in settings.api.cors_allow_origins.split(",") if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Request context
    app.add_middleware(RequestContextMiddleware)
    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


async def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    return Response(
        content='{"detail":"rate limit exceeded"}',
        status_code=429,
        media_type="application/json",
    )
