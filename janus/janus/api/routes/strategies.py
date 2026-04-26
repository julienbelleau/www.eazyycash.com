"""Strategy control endpoints.

GET    /v1/strategies                  — list strategies + state
POST   /v1/strategies/{id}/pause       — kill switch (write scope required)
POST   /v1/strategies/{id}/resume      — resume after a pause
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from janus.api.auth import TenantContext, get_tenant_context, require_write
from janus.regime.regime_router import StrategyId
from janus.risk.kill_switches import KillScope, KillSwitchRegistry


router = APIRouter(prefix="/v1/strategies", tags=["strategies"])


# Process-level singleton — in production the engine and API run in separate
# processes, so the registry is sourced from Redis (see api.state_store).
# Phase 1 of SaaS-ification keeps it in-memory; this is enough to test the
# contract.
_REGISTRY = KillSwitchRegistry()


def get_registry() -> KillSwitchRegistry:
    return _REGISTRY


class StrategyView(BaseModel):
    id: str
    paused: bool
    paused_reason: str | None
    paused_at: datetime | None


class PauseRequest(BaseModel):
    reason: str = "manual pause via api"


@router.get("", response_model=list[StrategyView])
async def list_strategies(
    ctx: TenantContext = Depends(get_tenant_context),
    registry: KillSwitchRegistry = Depends(get_registry),
) -> list[StrategyView]:
    out: list[StrategyView] = []
    for sid in StrategyId:
        active = next(
            (e for e in registry.active() if e.scope is KillScope.STRATEGY and e.target == sid.value),
            None,
        )
        out.append(StrategyView(
            id=sid.value, paused=active is not None,
            paused_reason=active.reason if active else None,
            paused_at=active.triggered_at if active else None,
        ))
    return out


@router.post("/{strategy_id}/pause")
async def pause_strategy(
    strategy_id: str,
    body: PauseRequest,
    ctx: TenantContext = Depends(require_write),
    registry: KillSwitchRegistry = Depends(get_registry),
) -> dict[str, object]:
    if strategy_id not in {s.value for s in StrategyId}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown strategy")
    event = registry.trip(KillScope.STRATEGY, strategy_id, body.reason)
    return {"strategy_id": strategy_id, "paused_at": event.triggered_at, "reason": event.reason}


@router.post("/{strategy_id}/resume")
async def resume_strategy(
    strategy_id: str,
    ctx: TenantContext = Depends(require_write),
    registry: KillSwitchRegistry = Depends(get_registry),
) -> dict[str, object]:
    if strategy_id not in {s.value for s in StrategyId}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown strategy")
    registry.reset(KillScope.STRATEGY, strategy_id)
    return {"strategy_id": strategy_id, "resumed_at": datetime.now(timezone.utc)}
