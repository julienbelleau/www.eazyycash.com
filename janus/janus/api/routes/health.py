"""Health + readiness probes.

`/healthz` — process is alive (cheap, doesn't touch DB).
`/readyz`  — dependencies are reachable (DB + Redis), used by Railway healthchecks.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from janus import __version__
from janus.api.db import get_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc.__class__.__name__}"
    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ready" if healthy else "degraded", "checks": checks}


@router.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "janus-api",
        "version": __version__,
        "docs": "/docs",
        "health": "/healthz",
    }
