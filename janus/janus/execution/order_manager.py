"""Order state machine.

Per plan §9: PENDING → SUBMITTED → FILLED/PARTIAL/CANCELLED/REJECTED.
Each order has an immutable `client_order_id` (UUID) — exchange-side acks
are matched back via this. State transitions are fully recorded so any
order can be replayed post-hoc for audit.

Idempotence: re-submitting the same client_order_id is a no-op (the broker
returns the existing exchange-id). This is critical for retry safety after
network glitches.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from loguru import logger

from janus.errors import PermanentError, TransientError
from janus.strategies.base import Order


class OrderStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(slots=True)
class ManagedOrder:
    order: Order
    status: OrderStatus = OrderStatus.PENDING
    exchange_order_id: str | None = None
    filled_qty: Decimal = Decimal(0)
    avg_fill_price: Decimal = Decimal(0)
    submitted_at: datetime | None = None
    last_update_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: list[tuple[datetime, OrderStatus, str]] = field(default_factory=list)

    def transition(self, new_status: OrderStatus, note: str = "") -> None:
        now = datetime.now(timezone.utc)
        self.history.append((now, new_status, note))
        self.status = new_status
        self.last_update_at = now


class OrderManager:
    """In-memory state-machine layer in front of the broker.

    The broker is anything implementing `submit/cancel/fetch_status` — paper,
    CCXT live, or a test stub.
    """

    def __init__(self, broker: Any):
        self._broker = broker
        self._orders: dict[UUID, ManagedOrder] = {}
        self._lock = asyncio.Lock()

    @property
    def open_orders(self) -> list[ManagedOrder]:
        return [
            o for o in self._orders.values()
            if o.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)
        ]

    async def submit(self, order: Order, *, mark: Decimal, ctx: dict[str, Any]) -> ManagedOrder:
        async with self._lock:
            existing = self._orders.get(order.client_order_id)
            if existing is not None:
                # Idempotence: same client_order_id = no-op.
                logger.bind(coid=str(order.client_order_id)).warning("duplicate submit, ignoring")
                return existing
            mo = ManagedOrder(order=order)
            mo.transition(OrderStatus.PENDING, "queued")
            self._orders[order.client_order_id] = mo

        try:
            fill = self._broker.submit(order, mark=mark, ctx=ctx, ts=datetime.now(timezone.utc))
            mo.exchange_order_id = str(getattr(fill, "client_order_id", order.client_order_id))
            mo.filled_qty = order.qty
            mo.avg_fill_price = fill.fill_price
            mo.transition(OrderStatus.FILLED, f"filled @ {fill.fill_price}")
            return mo
        except TransientError as exc:
            mo.transition(OrderStatus.PENDING, f"transient: {exc}")
            raise
        except PermanentError as exc:
            mo.transition(OrderStatus.REJECTED, f"rejected: {exc}")
            raise

    async def cancel(self, client_order_id: UUID) -> bool:
        mo = self._orders.get(client_order_id)
        if mo is None or mo.status not in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
            return False
        try:
            self._broker.cancel(client_order_id)
        except Exception as exc:  # noqa: BLE001
            mo.transition(OrderStatus.SUBMITTED, f"cancel failed: {exc}")
            return False
        mo.transition(OrderStatus.CANCELLED, "user cancel")
        return True
