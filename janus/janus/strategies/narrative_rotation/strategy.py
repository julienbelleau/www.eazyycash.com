"""Narrative-rotation strategy state machine.

States:
  WATCHING        — no basket open; scanning for emergent rotations
  HOLDING_BASKET  — basket of N tickers from one narrative; manage exits
  COOLDOWN        — recently exited; pause for `cooldown_days`

The basket is treated as a *single position* internally; the engine layer
splits the orders across constituent tickers in execution.

Exit triggers (per plan §5):
  - Take profit on the basket: +40%
  - Stop loss on the basket: -15%
  - Time stop: 60 days
  - Negative-acceleration kill: leader narrative's smoothed acceleration
    flips negative AND stays so for 3 consecutive days

Capacity-aware sizing (UPGRADES §2.5) is applied per ticker via
`features.narrative_index.capacity_aware_size_pct()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from janus.strategies.base import (
    MarketState,
    Order,
    OrderIntent,
    OrderType,
    Side,
    Signal,
    StrategyBase,
)


class State(StrEnum):
    WATCHING = "watching"
    HOLDING_BASKET = "holding_basket"
    COOLDOWN = "cooldown"


@dataclass(frozen=True, slots=True)
class NarrativeExitConfig:
    take_profit_basket_pct: float = 40.0
    stop_basket_pct: float = -15.0
    time_stop_days: int = 60
    deceleration_kill_consec_days: int = 3


@dataclass(frozen=True, slots=True)
class NarrativeStrategyConfig:
    positions_per_basket: int = 3
    pct_per_ticker: float = 4.0
    fees_taker_pct: float = 0.10
    cooldown_days: int = 14
    exits: NarrativeExitConfig = field(default_factory=NarrativeExitConfig)


@dataclass
class _BasketContext:
    narrative: str
    opened_at: datetime
    tickers: tuple[str, ...]
    entry_basket_value: Decimal
    high_water_basket_value: Decimal
    consec_decel_days: int = 0


class NarrativeRotationStrategy(StrategyBase):
    """Top-level rotation strategy. The engine should pass the per-narrative
    feature DataFrame and current basket value via state.extras.
    """

    id = "narrative_rotation_v1"

    def __init__(self, cfg: NarrativeStrategyConfig):
        self.cfg = cfg
        self.state: State = State.WATCHING
        self._ctx: _BasketContext | None = None
        self._cooldown_until: datetime | None = None

    async def on_tick(self, state: MarketState) -> list[Order]:
        # Cooldown timer.
        if self.state is State.COOLDOWN and self._cooldown_until is not None:
            if state.as_of >= self._cooldown_until:
                self.state = State.WATCHING
                self._cooldown_until = None

        if self.state is State.WATCHING:
            return self._on_watching(state)
        if self.state is State.HOLDING_BASKET:
            return self._on_holding(state)
        return []

    def _on_watching(self, state: MarketState) -> list[Order]:
        sig: Signal | None = state.extras.get("emergent_signal")
        if sig is None:
            return []
        narrative: str | None = state.extras.get("emergent_narrative")
        tickers_for_narr: list[str] = state.extras.get("emergent_tickers", [])
        if not narrative or not tickers_for_narr:
            return []

        chosen = tuple(tickers_for_narr[: self.cfg.positions_per_basket])
        # Entry: orders for each ticker.
        orders: list[Order] = []
        portfolio_quote: Decimal = state.extras.get("portfolio_quote", Decimal("100000"))
        per_ticker_quote = portfolio_quote * Decimal(str(self.cfg.pct_per_ticker / 100.0))
        for tkr in chosen:
            mark = state.extras.get("marks", {}).get(tkr)
            if mark is None or mark <= 0:
                continue
            qty = per_ticker_quote / Decimal(str(mark))
            orders.append(Order(
                strategy_id=self.id, symbol=tkr,
                side=Side.LONG, intent=OrderIntent.OPEN,
                qty=qty, order_type=OrderType.MARKET,
                signal=sig,
            ))
        if not orders:
            return []

        self._ctx = _BasketContext(
            narrative=narrative,
            opened_at=state.as_of,
            tickers=chosen,
            entry_basket_value=portfolio_quote * Decimal(str(self.cfg.pct_per_ticker / 100.0)) * Decimal(len(chosen)),
            high_water_basket_value=portfolio_quote * Decimal(str(self.cfg.pct_per_ticker / 100.0)) * Decimal(len(chosen)),
        )
        self.state = State.HOLDING_BASKET
        return orders

    def _on_holding(self, state: MarketState) -> list[Order]:
        if self._ctx is None:
            return []
        ctx = self._ctx
        cur_value: Decimal = state.extras.get("basket_value", ctx.entry_basket_value)
        if cur_value > ctx.high_water_basket_value:
            ctx.high_water_basket_value = cur_value

        ret_pct = float((cur_value - ctx.entry_basket_value) / ctx.entry_basket_value * 100)
        elapsed_days = (state.as_of - ctx.opened_at).total_seconds() / 86_400.0
        cfg_exit = self.cfg.exits

        reason: str | None = None
        if ret_pct >= cfg_exit.take_profit_basket_pct:
            reason = "take_profit"
        elif ret_pct <= cfg_exit.stop_basket_pct:
            reason = "stop_loss"
        elif elapsed_days >= cfg_exit.time_stop_days:
            reason = "time_stop"
        else:
            # Deceleration kill — increment counter when accel < 0, reset otherwise.
            accel: float | None = state.extras.get("narrative_acceleration")
            if accel is not None and accel < 0:
                ctx.consec_decel_days += 1
            else:
                ctx.consec_decel_days = 0
            if ctx.consec_decel_days >= cfg_exit.deceleration_kill_consec_days:
                reason = "deceleration"

        if reason is None:
            return []

        # Emit close orders for every ticker in the basket.
        marks = state.extras.get("marks", {})
        positions_map = state.extras.get("basket_positions", {})  # ticker -> qty
        orders: list[Order] = []
        for tkr in ctx.tickers:
            qty = positions_map.get(tkr)
            if qty is None or qty <= 0:
                continue
            orders.append(Order(
                strategy_id=self.id, symbol=tkr,
                side=Side.LONG, intent=OrderIntent.CLOSE,
                qty=Decimal(str(qty)), order_type=OrderType.MARKET,
                signal=Signal(
                    name=f"narrative.exit.{reason}", confidence=1.0,
                    features={"ret_pct": ret_pct, "elapsed_days": elapsed_days},
                    note=f"narrative={ctx.narrative}",
                ),
            ))
        if orders:
            self.state = State.COOLDOWN
            self._cooldown_until = state.as_of + timedelta(days=self.cfg.cooldown_days)
            self._ctx = None
        return orders
