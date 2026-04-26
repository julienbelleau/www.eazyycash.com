"""Trade journal browsing — read fills for a (strategy, date)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from janus.api.auth import TenantContext, get_tenant_context
from janus.monitoring.trade_journal import TradeJournal

router = APIRouter(prefix="/v1/journal", tags=["journal"])


@router.get("/{strategy_id}/{date}")
async def read_journal(
    strategy_id: str,
    date: str,
    ctx: TenantContext = Depends(get_tenant_context),
    journal_dir: Path = Query(default=Path("./paper-journal"), include_in_schema=False),
    limit: int = Query(default=200, le=1000),
) -> dict[str, Any]:
    target = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    journal = TradeJournal(journal_dir)
    records = journal.read_day(target, strategy_id=strategy_id)
    return {
        "strategy_id": strategy_id,
        "date": date,
        "count": len(records),
        "records": records[:limit],
    }
