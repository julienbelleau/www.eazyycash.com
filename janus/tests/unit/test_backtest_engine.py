"""Backtest engine end-to-end with a stub strategy.

We don't run the real Refractory strategy here — the engine's correctness is
about state-tracking, not signal logic. We use a deterministic stub that
opens at minute 5 and closes at minute 50.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import polars as pl
import pytest

from janus.backtest.data_provider import InMemoryWindowProvider
from janus.backtest.engine import BacktestEngine
from janus.backtest.slippage import SquareRootImpactSlippage
from janus.strategies.base import (
    MarketState,
    Order,
    OrderIntent,
    OrderType,
    Side,
    Signal,
    StrategyBase,
)


def _bars_df(start: datetime, n: int, base_price: float = 40_000.0) -> pl.DataFrame:
    rows = []
    for i in range(n):
        ts = start + timedelta(minutes=i)
        # Drift up 5 USD per minute — opens long, profits.
        close = base_price + i * 5
        rows.append({
            "symbol": "BTCUSDT", "ts": ts,
            "open": close - 1.0, "high": close + 5.0, "low": close - 5.0, "close": close,
            "volume": 50.0, "quote_volume": 50.0 * close, "trade_count": 100,
            "taker_buy_volume": 25.0, "taker_buy_quote_volume": 25.0 * close,
        })
    return pl.DataFrame(rows)


class _StubStrategy(StrategyBase):
    id = "stub"

    def __init__(self) -> None:
        self.opened = False
        self.closed = False

    async def on_tick(self, state: MarketState) -> list[Order]:
        i = (state.as_of - datetime(2024, 1, 1, tzinfo=timezone.utc)).total_seconds() / 60.0
        if i == 5 and not self.opened:
            self.opened = True
            return [Order(
                strategy_id=self.id, symbol=state.symbol,
                side=Side.LONG, intent=OrderIntent.OPEN,
                qty=Decimal("0.1"), order_type=OrderType.MARKET,
                signal=Signal(name="stub.open", confidence=1.0, features={}),
            )]
        if i == 50 and self.opened and not self.closed and state.open_position is not None:
            self.closed = True
            return [Order(
                strategy_id=self.id, symbol=state.symbol,
                side=Side.LONG, intent=OrderIntent.CLOSE,
                qty=state.open_position.qty, order_type=OrderType.MARKET,
                signal=Signal(name="stub.close", confidence=1.0, features={}),
            )]
        return []


@pytest.mark.asyncio()
async def test_engine_runs_stub_strategy_and_records_trade() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = _bars_df(start, n=120)
    data = InMemoryWindowProvider(bars=bars)

    engine = BacktestEngine(
        symbol="BTCUSDT",
        strategy=_StubStrategy(),
        data=data,
        slippage=SquareRootImpactSlippage(fee_bps=0.0),
        starting_cash=Decimal("100000"),
    )
    result = await engine.run(start=start, end=start + timedelta(minutes=119))

    assert len(result.trades) == 1
    # Bought low (~40025), sold higher (~40250) — must be profitable.
    assert result.trades[0].pnl_quote > 0
    assert result.equity[-1] > result.equity[0]


@pytest.mark.asyncio()
async def test_engine_no_trades_no_open_position() -> None:
    class _NoopStrategy(StrategyBase):
        id = "noop"

        async def on_tick(self, state: MarketState) -> list[Order]:
            return []

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    data = InMemoryWindowProvider(bars=_bars_df(start, 60))
    engine = BacktestEngine(
        symbol="BTCUSDT", strategy=_NoopStrategy(), data=data,
        slippage=SquareRootImpactSlippage(),
    )
    result = await engine.run(start=start, end=start + timedelta(minutes=59))
    assert result.trades == []
    # Equity stays flat (cash only).
    assert result.equity[0] == result.equity[-1]
