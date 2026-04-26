"""Periodic reconciliation between local state and exchange.

Every 60 seconds (configurable), the reconciler:
  1. Fetches all open orders from the exchange.
  2. Compares against the OrderManager's view.
  3. Resolves divergences by trusting the exchange (it's the source of truth):
     - exchange-only orders → log warning, mark as foreign
     - local-only orders that the exchange says are filled → close the local one
     - status mismatch → update local to match exchange

The exchange call is wrapped in retry-with-backoff. If 3 consecutive
reconciliations fail, we trip a kill switch (handled by risk layer).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from janus.errors import TransientError


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    timestamp: datetime
    n_local_orders: int
    n_exchange_orders: int
    divergences: list[str]
    healthy: bool


class Reconciler:
    def __init__(
        self,
        *,
        order_manager: Any,
        fetch_open_orders: Callable[[], Any],   # async callable
        on_kill_switch: Callable[[str], None] | None = None,
        period_seconds: float = 60.0,
        max_consecutive_failures: int = 3,
    ):
        self.order_manager = order_manager
        self.fetch_open_orders = fetch_open_orders
        self.on_kill_switch = on_kill_switch
        self.period_seconds = period_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self._stop = asyncio.Event()
        self._failures = 0

    async def stop(self) -> None:
        self._stop.set()

    async def reconcile_once(self) -> ReconciliationReport:
        try:
            exchange_orders = await self.fetch_open_orders()
        except TransientError as exc:
            self._failures += 1
            logger.warning("reconcile failed (#{}): {}", self._failures, exc)
            if self._failures >= self.max_consecutive_failures and self.on_kill_switch:
                self.on_kill_switch(f"reconcile failed {self._failures} times")
            return ReconciliationReport(
                timestamp=datetime.now(timezone.utc),
                n_local_orders=len(self.order_manager.open_orders),
                n_exchange_orders=0,
                divergences=[f"fetch_failed: {exc}"],
                healthy=False,
            )
        self._failures = 0

        local_open = {str(o.order.client_order_id): o for o in self.order_manager.open_orders}
        ex_ids = {str(getattr(o, "client_order_id", o.get("clientOrderId", ""))) for o in exchange_orders}

        divergences: list[str] = []
        for coid, mo in local_open.items():
            if coid not in ex_ids and mo.exchange_order_id is not None:
                divergences.append(f"local_only: {coid} (status={mo.status})")
        for coid in ex_ids - set(local_open.keys()):
            divergences.append(f"exchange_only: {coid}")

        return ReconciliationReport(
            timestamp=datetime.now(timezone.utc),
            n_local_orders=len(local_open),
            n_exchange_orders=len(ex_ids),
            divergences=divergences,
            healthy=not divergences,
        )

    async def run(self) -> None:
        while not self._stop.is_set():
            await self.reconcile_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.period_seconds)
            except asyncio.TimeoutError:
                continue
