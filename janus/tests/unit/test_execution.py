"""Order manager + smart router + slippage tracker + reconciliation tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from janus.execution.order_manager import OrderManager, OrderStatus
from janus.execution.reconciliation import Reconciler
from janus.execution.slippage_tracker import SlippageTracker
from janus.execution.smart_router import (
    RoutingPolicy,
    almgren_chriss_schedule,
    naive_twap_schedule,
    schedule_for,
    should_split,
)
from janus.strategies.base import Order, OrderIntent, OrderType, Side


class _StubBroker:
    def __init__(self, raise_exc: Exception | None = None) -> None:
        self.raise_exc = raise_exc
        self.submitted: list[Order] = []
        self.cancelled: list[str] = []

    def submit(self, order: Order, *, mark: Decimal, ctx: dict[str, Any], ts: datetime) -> Any:
        if self.raise_exc:
            raise self.raise_exc
        self.submitted.append(order)
        from janus.paper.simulator import PaperFill
        return PaperFill(
            client_order_id=order.client_order_id,
            fill_price=mark, qty=order.qty, ts=ts, slippage_bps=4.0,
        )

    def cancel(self, client_order_id: object) -> None:
        self.cancelled.append(str(client_order_id))


@pytest.mark.asyncio()
async def test_order_manager_submits_and_marks_filled() -> None:
    broker = _StubBroker()
    om = OrderManager(broker)
    o = Order(strategy_id="x", symbol="BTCUSDT", side=Side.LONG,
              intent=OrderIntent.OPEN, qty=Decimal("0.1"),
              order_type=OrderType.MARKET)
    mo = await om.submit(o, mark=Decimal("40000"), ctx={})
    assert mo.status is OrderStatus.FILLED
    assert mo.filled_qty == Decimal("0.1")


@pytest.mark.asyncio()
async def test_order_manager_idempotent_resubmit() -> None:
    broker = _StubBroker()
    om = OrderManager(broker)
    o = Order(strategy_id="x", symbol="BTCUSDT", side=Side.LONG,
              intent=OrderIntent.OPEN, qty=Decimal("0.1"),
              order_type=OrderType.MARKET)
    mo1 = await om.submit(o, mark=Decimal("40000"), ctx={})
    mo2 = await om.submit(o, mark=Decimal("40000"), ctx={})
    assert mo1 is mo2
    assert len(broker.submitted) == 1


def test_naive_twap_returns_equal_slices() -> None:
    sch = naive_twap_schedule(Decimal("4"), n_slices=4, minutes_total=20)
    assert len(sch) == 4
    assert all(q == Decimal("1") for q, _ in sch)
    minutes = [m for _, m in sch]
    assert minutes == sorted(minutes)


def test_almgren_chriss_schedule_sums_to_total() -> None:
    sch = almgren_chriss_schedule(Decimal("10"), n_slices=4, minutes_total=20,
                                    sigma=0.02, eta=0.5, lambda_=1e-4)
    total = sum(q for q, _ in sch)
    assert abs(float(total) - 10.0) < 0.05


def test_should_split_threshold() -> None:
    pol = RoutingPolicy(large_position_quote=Decimal("1000"))
    assert not should_split(Decimal("500"), pol)
    assert should_split(Decimal("5000"), pol)


def test_schedule_for_no_split_when_small() -> None:
    sch = schedule_for(Decimal("0.001"), mark=Decimal("40000"),
                       policy=RoutingPolicy(large_position_quote=Decimal("100")))
    assert len(sch) == 1


def test_slippage_tracker_alerts_on_drift() -> None:
    tr = SlippageTracker(window=10, drift_factor_alert=1.5, drift_factor_kill=3.0)
    for _ in range(10):
        tr.record(expected_bps=10.0, realised_bps=20.0)  # 2× drift
    assert tr.should_alert()
    assert not tr.should_kill()


def test_slippage_tracker_kill_at_3x() -> None:
    tr = SlippageTracker(window=10, drift_factor_kill=3.0, drift_factor_alert=1.5)
    for _ in range(10):
        tr.record(expected_bps=5.0, realised_bps=20.0)  # 4× drift
    assert tr.should_kill()


@pytest.mark.asyncio()
async def test_reconciler_healthy_when_aligned() -> None:
    om = OrderManager(_StubBroker())
    async def fetch() -> list[Any]:
        return []
    rec = Reconciler(order_manager=om, fetch_open_orders=fetch)
    report = await rec.reconcile_once()
    assert report.healthy
    assert report.divergences == []


@pytest.mark.asyncio()
async def test_reconciler_trips_kill_after_consecutive_failures() -> None:
    om = OrderManager(_StubBroker())
    from janus.errors import ExchangeUnavailableError
    async def fetch() -> list[Any]:
        raise ExchangeUnavailableError("network down")
    tripped: list[str] = []
    rec = Reconciler(
        order_manager=om, fetch_open_orders=fetch,
        on_kill_switch=lambda r: tripped.append(r),
        max_consecutive_failures=2,
    )
    await rec.reconcile_once()
    await rec.reconcile_once()
    assert tripped, "kill switch should have tripped after 2 failures"
