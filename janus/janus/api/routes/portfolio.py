"""Portfolio overview + positions + P&L endpoints.

These endpoints are read-only and require any authenticated tenant. The
underlying data comes from the engine state, which the API process loads
from Redis snapshots written by the worker processes (see
`janus/engine/state_publisher.py` for the contract — Phase 2 of the SaaS
work). Until that's wired, the routes return shapes from the trade journal
and the in-DB realised PnL, which is enough to validate the API contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from janus.api.auth import TenantContext, get_tenant_context
from janus.api.db import get_session
from janus.monitoring.trade_journal import TradeJournal


router = APIRouter(prefix="/v1/portfolio", tags=["portfolio"])


class PortfolioSummary(BaseModel):
    tenant_id: str
    realised_pnl_quote: Decimal
    open_positions: int
    last_update: datetime


class StrategyAttribution(BaseModel):
    strategy_id: str
    realised_pnl_quote: Decimal
    open_positions: int
    n_trades_today: int


@router.get("/summary", response_model=PortfolioSummary)
async def summary(
    ctx: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_session),
) -> PortfolioSummary:
    # Until the engine writes a snapshot table, derive a minimal view from
    # ingest_jobs presence (proves the system is running).
    res = await session.execute(text("SELECT NOW() AS now"))
    now = res.scalar() or datetime.now(timezone.utc)
    return PortfolioSummary(
        tenant_id=ctx.tenant.id,
        realised_pnl_quote=Decimal(0),
        open_positions=0,
        last_update=now,
    )


@router.get("/attribution", response_model=list[StrategyAttribution])
async def attribution(
    ctx: TenantContext = Depends(get_tenant_context),
    journal_dir: Path = Query(default=Path("./paper-journal"), include_in_schema=False),
) -> list[StrategyAttribution]:
    journal = TradeJournal(journal_dir)
    today_records = journal.read_day(datetime.now(timezone.utc))
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for r in today_records:
        by_strategy.setdefault(str(r["strategy_id"]), []).append(r)
    return [
        StrategyAttribution(
            strategy_id=sid,
            realised_pnl_quote=Decimal(0),    # populated when engine snapshot lands
            open_positions=0,
            n_trades_today=len([r for r in fills if r.get("intent") == "close"]),
        )
        for sid, fills in by_strategy.items()
    ]
