"""Engine runtime — multiplexes strategies behind regime gating + risk overlay.

Per tick, for each registered strategy:
  1. Check kill switches → skip if tripped
  2. Check regime gating → skip if weight is 0
  3. Apply correlation + drawdown adjustments to the strategy's allocation
  4. Build the strategy's MarketState, call on_tick()
  5. Route returned orders through the OrderManager
  6. Update equity history, kill-switch trippers, monitors

The engine is *transport-agnostic*: it pulls market data from a provider and
talks to a broker abstraction. Both have backtest, paper, and live impls.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from loguru import logger

from janus.backtest.data_provider import MarketWindowProvider
from janus.execution.order_manager import OrderManager
from janus.regime.regime_router import GatingDecision, StrategyId
from janus.risk.correlation_monitor import CorrelationMonitor
from janus.risk.drawdown_manager import DrawdownManager
from janus.risk.kill_switches import KillScope, KillSwitchRegistry
from janus.strategies.base import MarketState, Order, StrategyBase


@dataclass
class StrategyRegistration:
    strategy: StrategyBase
    symbols: tuple[str, ...]
    cascade_lookback: timedelta = timedelta(minutes=60)


@dataclass
class EngineState:
    portfolio_quote: Decimal = Decimal("100000")
    realized_pnl: Decimal = Decimal(0)
    daily_pnl_by_strategy: dict[str, list[float]] = field(default_factory=dict)


class EngineRuntime:
    def __init__(
        self,
        *,
        data: MarketWindowProvider,
        order_manager: OrderManager,
        kill_switches: KillSwitchRegistry,
        drawdown: DrawdownManager,
        correlation: CorrelationMonitor,
        starting_quote: Decimal = Decimal("100000"),
    ):
        self.data = data
        self.om = order_manager
        self.kill = kill_switches
        self.dd = drawdown
        self.corr = correlation
        self.state = EngineState(portfolio_quote=starting_quote)
        self._strategies: dict[str, StrategyRegistration] = {}

    def register(self, registration: StrategyRegistration) -> None:
        self._strategies[registration.strategy.id] = registration

    async def step(self, ts: datetime, gating: GatingDecision) -> None:
        if self.kill.is_tripped(KillScope.PORTFOLIO, "global"):
            logger.warning("portfolio kill switch active — skipping step")
            return

        peers = list(self._strategies.keys())
        for sid, reg in self._strategies.items():
            sid_enum = StrategyId(sid)
            gate_w = gating.weight_for(sid_enum)
            if gate_w <= 0:
                continue
            if self.kill.is_tripped(KillScope.STRATEGY, sid):
                continue

            # Correlation + drawdown overlays.
            corr_adj = self.corr.adjustment_for(sid, peers)
            dd_action = self.dd.update_strategy(sid, float(self.state.portfolio_quote))
            if dd_action.halt_portfolio:
                self.kill.trip(KillScope.PORTFOLIO, "global", "portfolio drawdown halt")
                return
            multiplier = gate_w * corr_adj * dd_action.multiplier
            if multiplier <= 0:
                continue

            for symbol in reg.symbols:
                window = self.data.get_window(symbol, ts, reg.cascade_lookback)
                if not window.bars:
                    continue
                last_close = Decimal(str(window.bars[-1]["close"]))
                state = MarketState(
                    as_of=ts, symbol=symbol, last_price=last_close,
                    open_position=None,   # multi-position book lives in OrderManager
                    extras={
                        "window": window,
                        "baseline_bars": self.data.get_baseline_bars(symbol, ts),
                        "portfolio_quote": self.state.portfolio_quote * Decimal(str(multiplier)),
                    },
                )
                orders = await reg.strategy.on_tick(state)
                for order in orders:
                    await self.om.submit(order, mark=last_close, ctx={})
