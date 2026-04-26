"""Regime + gating endpoints.

Phase 1 of SaaS work returns the static base weights — once the engine
publishes its regime snapshot to Redis, this endpoint will read live values.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from janus.api.auth import TenantContext, get_tenant_context
from janus.regime.regime_router import StrategyId, gate
from janus.regime.hmm_detector import Regime

router = APIRouter(prefix="/v1/regime", tags=["regime"])


class RegimeView(BaseModel):
    regime: str
    weights: dict[str, float]
    is_transitioning: bool
    confidence: float


@router.get("", response_model=RegimeView)
async def current_regime(
    ctx: TenantContext = Depends(get_tenant_context),
) -> RegimeView:
    # Stub — future: read from `regime:current` redis key written by the worker.
    decision = gate(Regime.RANGE, confidence=1.0, is_transitioning=False)
    return RegimeView(
        regime=decision.regime.value,
        weights={sid.value: decision.weight_for(sid) for sid in StrategyId},
        is_transitioning=False,
        confidence=1.0,
    )
