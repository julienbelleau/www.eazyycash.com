"""Event-driven backtest engine.

Design:
- One symbol per engine instance (multi-symbol coordination is the engine
  layer's job, not the backtest's).
- Tick cadence drives the loop. Each tick, the engine:
    1. Builds the MarketWindow from the data provider (point-in-time)
    2. Calls strategy.on_tick(state)
    3. Routes any returned orders through the slippage model
    4. Updates positions and equity
- All times are UTC. All prices/quantities are Decimal to avoid float drift
  on long horizons.

Determinism: identical inputs → identical equity curves → identical metrics.
This is the property that makes regression-testing the strategy meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import numpy as np

from janus.backtest.data_provider import MarketWindowProvider
from janus.backtest.metrics import TradeRecord
from janus.backtest.slippage import SlippageModel
from janus.strategies.base import (
    MarketState,
    Order,
    OrderIntent,
    Position,
    Side,
    StrategyBase,
)


@dataclass(slots=True)
class _BacktestState:
    cash: Decimal
    position: Position | None = None
    realized_pnl: Decimal = Decimal(0)
    equity_history: list[tuple[datetime, Decimal]] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)
    open_entry_price: Decimal | None = None
    open_qty: Decimal | None = None


@dataclass(slots=True)
class BacktestResult:
    timestamps: list[datetime]
    equity: np.ndarray
    trades: list[TradeRecord]
    final_cash: Decimal


class BacktestEngine:
    def __init__(
        self,
        *,
        symbol: str,
        strategy: StrategyBase,
        data: MarketWindowProvider,
        slippage: SlippageModel,
        cascade_lookback: timedelta = timedelta(minutes=60),
        starting_cash: Decimal = Decimal("100000"),
    ):
        self.symbol = symbol
        self.strategy = strategy
        self.data = data
        self.slippage = slippage
        self.cascade_lookback = cascade_lookback
        self.state = _BacktestState(cash=starting_cash)

    def _equity(self, mark: Decimal) -> Decimal:
        if self.state.position is None:
            return self.state.cash
        return self.state.cash + self.state.position.unrealized_pnl(mark) + (
            self.state.position.qty * self.state.position.avg_entry_price
        )

    async def _execute(self, order: Order, mark: Decimal, ts: datetime,
                       extras: dict[str, Any]) -> None:
        side = "long" if order.side is Side.LONG else "short"
        fill = self.slippage.fill(side=side, mark=mark, qty=order.qty, ctx=extras)

        if order.intent is OrderIntent.OPEN:
            # Spend cash, open position.
            self.state.cash -= fill.fill_price * order.qty
            self.state.position = Position(
                symbol=self.symbol,
                side=order.side,
                qty=order.qty,
                avg_entry_price=fill.fill_price,
                opened_at=ts,
                strategy_id=order.strategy_id,
                take_profit=order.take_profit,
                stop_loss=order.stop_loss,
            )
            self.state.open_entry_price = fill.fill_price
            self.state.open_qty = order.qty
        else:
            # Close — return cash, realise P&L.
            assert self.state.position is not None, "close without an open position"
            entry = self.state.position.avg_entry_price
            qty = self.state.position.qty
            sign = Decimal(1) if order.side is Side.LONG else Decimal(-1)
            pnl = (fill.fill_price - entry) * qty * sign
            self.state.cash += fill.fill_price * qty
            self.state.realized_pnl += pnl
            return_pct = float(pnl / (entry * qty)) if entry * qty != 0 else 0.0
            self.state.trades.append(TradeRecord(
                pnl_quote=float(pnl),
                return_pct=return_pct,
                entry_ts_utc_minute=int(self.state.position.opened_at.timestamp() // 60),
                exit_ts_utc_minute=int(ts.timestamp() // 60),
            ))
            self.state.position = None

    async def run(self, *, start: datetime, end: datetime, step: timedelta = timedelta(minutes=1)) -> BacktestResult:
        ts = start
        timestamps: list[datetime] = []
        while ts <= end:
            window = self.data.get_window(self.symbol, ts, self.cascade_lookback)
            if not window.bars:
                ts += step
                continue
            last_close = Decimal(str(window.bars[-1]["close"]))

            baseline = self.data.get_baseline_bars(self.symbol, ts)

            state = MarketState(
                as_of=ts,
                symbol=self.symbol,
                last_price=last_close,
                open_position=self.state.position,
                extras={"window": window, "baseline_bars": baseline},
            )
            orders = await self.strategy.on_tick(state)
            for order in orders:
                await self._execute(order, last_close, ts, extras={})

            equity = self._equity(last_close)
            self.state.equity_history.append((ts, equity))
            timestamps.append(ts)
            ts += step

        equity_arr = np.array([float(e) for _, e in self.state.equity_history], dtype=float)
        return BacktestResult(
            timestamps=timestamps,
            equity=equity_arr,
            trades=list(self.state.trades),
            final_cash=self.state.cash,
        )
