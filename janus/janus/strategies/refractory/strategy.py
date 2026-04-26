"""Refractory-Period strategy state machine.

States:
  IDLE        — no cascade in progress, watching for cascade_detected
  IN_CASCADE  — cascade detected, waiting for exhaustion confirmation
  IN_TRADE    — long position open, managing exits
  COOLDOWN    — recently exited; ignore new cascade signals for `cooldown_minutes`

The strategy is purely reactive: every tick it consumes a `MarketState` plus
optional refractory-specific extras (the engine populates these from the
repository) and returns zero or more orders.

Exits implement the original plan §4 in their entirety, replicated below for
auditability:
  1. TP at retracement of `take_profit_retracement_pct` of the cascade drop
  2. OI recovery to `oi_recovery_pct` of pre-cascade level
  3. Funding rate normalization (z-score returns near 0)
  4. Time stop at `time_stop_hours` after entry
  5. Hard stop at `stop_loss_pct`
  6. Trailing stop activated above `trailing_activate_pct`, distance `trailing_distance_pct`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from janus.features import refractory_features as rf
from janus.strategies.base import (
    MarketState,
    Order,
    OrderIntent,
    OrderType,
    Side,
    StrategyBase,
)
from janus.strategies.refractory.signals import (
    CascadeDetector,
    CascadeThresholds,
    ExhaustionDetector,
    ExhaustionThresholds,
)


class State(StrEnum):
    IDLE = "idle"
    IN_CASCADE = "in_cascade"
    IN_TRADE = "in_trade"
    COOLDOWN = "cooldown"


@dataclass(frozen=True, slots=True)
class ExitConfig:
    take_profit_retracement_pct: float = 50.0
    oi_recovery_pct: float = 80.0
    stop_loss_pct: float = -2.0
    trailing_activate_pct: float = 1.5
    trailing_distance_pct: float = 1.0
    time_stop_hours: int = 24


@dataclass(frozen=True, slots=True)
class RefractoryConfig:
    symbol: str
    cascade: CascadeThresholds
    exhaustion: ExhaustionThresholds
    exits: ExitConfig
    cooldown_minutes: int = 240               # 4h cooldown after exit
    position_size_quote: Decimal = Decimal("1000")  # USD per trade in stub mode
                                                    # (real sizing comes from risk module)


@dataclass
class _CascadeContext:
    """State carried while we're in IN_CASCADE / IN_TRADE."""

    started_at: datetime
    pre_cascade_price: Decimal
    pre_cascade_oi: Decimal
    cascade_low_price: Decimal | None = None
    entry_price: Decimal | None = None
    entry_ts: datetime | None = None
    high_water_mark: Decimal | None = None    # for trailing stop


class RefractoryStrategy(StrategyBase):
    id = "refractory_v1"

    def __init__(self, cfg: RefractoryConfig):
        self.cfg = cfg
        self.state: State = State.IDLE
        self.cascade = CascadeDetector(cfg.symbol, cfg.cascade)
        self.exhaustion = ExhaustionDetector(cfg.symbol, cfg.exhaustion)
        self._ctx: _CascadeContext | None = None
        self._cooldown_until: datetime | None = None

    # The strategy receives precomputed feature windows from the engine
    # via state.extras["window"] and state.extras["baseline_bars"]. Strategies
    # never query the DB themselves.
    async def on_tick(self, state: MarketState) -> list[Order]:
        window: rf.MarketWindow = state.extras["window"]
        baseline_bars: list[dict[str, Any]] = state.extras["baseline_bars"]

        # Refresh the adaptive quantile every tick.
        self.cascade.update_thresholds(rf.liq_total_window(window))

        # Cooldown timer.
        if self.state is State.COOLDOWN and self._cooldown_until is not None:
            if state.as_of >= self._cooldown_until:
                self.state = State.IDLE
                self._cooldown_until = None

        # ─── IDLE → IN_CASCADE ───
        if self.state is State.IDLE:
            sig = self.cascade.evaluate(window, baseline_bars)
            if sig is not None:
                pre_oi = (
                    Decimal(str(window.open_interest[0]["oi_contracts"]))
                    if window.open_interest
                    else Decimal(0)
                )
                self._ctx = _CascadeContext(
                    started_at=state.as_of,
                    pre_cascade_price=Decimal(str(window.bars[0]["close"])),
                    pre_cascade_oi=pre_oi,
                )
                self.state = State.IN_CASCADE
                self.exhaustion.reset()
            return []

        # ─── IN_CASCADE → IN_TRADE ───
        if self.state is State.IN_CASCADE and self._ctx is not None:
            self.exhaustion.update(window)
            sig = self.exhaustion.evaluate(window)
            self._ctx.cascade_low_price = state.last_price if (
                self._ctx.cascade_low_price is None or state.last_price < self._ctx.cascade_low_price
            ) else self._ctx.cascade_low_price

            if sig is None:
                return []

            # Place entry order. Sizing is a stub — production wiring delegates to the risk module.
            qty = self._size_position(state.last_price)
            self._ctx.entry_price = state.last_price
            self._ctx.entry_ts = state.as_of
            self._ctx.high_water_mark = state.last_price
            self.state = State.IN_TRADE
            return [
                Order(
                    strategy_id=self.id,
                    symbol=state.symbol,
                    side=Side.LONG,
                    intent=OrderIntent.OPEN,
                    qty=qty,
                    order_type=OrderType.MARKET,
                    take_profit=self._take_profit_price(),
                    stop_loss=self._initial_stop_loss(state.last_price),
                    signal=sig,
                ),
            ]

        # ─── IN_TRADE → manage exits ───
        if self.state is State.IN_TRADE and self._ctx is not None and state.open_position is not None:
            exit_orders = self._manage_exits(state, window)
            if exit_orders:
                self.state = State.COOLDOWN
                self._cooldown_until = state.as_of + timedelta(minutes=self.cfg.cooldown_minutes)
            return exit_orders

        return []

    # ─────────────── helpers ───────────────

    def _size_position(self, mark: Decimal) -> Decimal:
        if mark <= 0:
            return Decimal(0)
        return self.cfg.position_size_quote / mark

    def _take_profit_price(self) -> Decimal | None:
        if self._ctx is None or self._ctx.cascade_low_price is None:
            return None
        retrace = Decimal(str(self.cfg.exits.take_profit_retracement_pct / 100.0))
        return self._ctx.cascade_low_price + (
            self._ctx.pre_cascade_price - self._ctx.cascade_low_price
        ) * retrace

    def _initial_stop_loss(self, entry: Decimal) -> Decimal:
        sl_frac = Decimal(str(self.cfg.exits.stop_loss_pct / 100.0))
        return entry * (Decimal(1) + sl_frac)

    def _manage_exits(self, state: MarketState, window: rf.MarketWindow) -> list[Order]:
        assert self._ctx is not None and state.open_position is not None
        ctx = self._ctx
        cfg = self.cfg.exits
        pos = state.open_position
        last = state.last_price

        # Update high-water mark for trailing stop.
        if ctx.high_water_mark is None or last > ctx.high_water_mark:
            ctx.high_water_mark = last

        # 1. Take profit (50% retracement).
        tp = self._take_profit_price()
        if tp is not None and last >= tp:
            return [self._make_exit_order(state, "take_profit_retracement")]

        # 2. OI recovery to N% of pre-cascade.
        if window.open_interest:
            cur_oi = Decimal(str(window.open_interest[-1]["oi_contracts"]))
            recovery_target = ctx.pre_cascade_oi * Decimal(str(cfg.oi_recovery_pct / 100.0))
            if cur_oi >= recovery_target:
                return [self._make_exit_order(state, "oi_recovered")]

        # 3. Funding normalisation (z-score back to ~0).
        z = rf.funding_zscore(window)
        if abs(z) < 0.25 and ctx.entry_ts is not None:
            elapsed_min = (state.as_of - ctx.entry_ts).total_seconds() / 60.0
            if elapsed_min > 60:  # don't trigger at the same tick as entry
                return [self._make_exit_order(state, "funding_normalised")]

        # 4. Time stop.
        if ctx.entry_ts is not None:
            elapsed_h = (state.as_of - ctx.entry_ts).total_seconds() / 3600.0
            if elapsed_h >= cfg.time_stop_hours:
                return [self._make_exit_order(state, "time_stop")]

        # 5. Hard stop loss.
        if pos.stop_loss is not None and last <= pos.stop_loss:
            return [self._make_exit_order(state, "stop_loss")]

        # 6. Trailing stop.
        if ctx.entry_price is not None:
            ret_pct = (last - ctx.entry_price) / ctx.entry_price * Decimal(100)
            if ret_pct >= Decimal(str(cfg.trailing_activate_pct)):
                trail_distance = ctx.high_water_mark * Decimal(str(cfg.trailing_distance_pct / 100.0))
                if last <= ctx.high_water_mark - trail_distance:
                    return [self._make_exit_order(state, "trailing_stop")]

        return []

    def _make_exit_order(self, state: MarketState, reason: str) -> Order:
        assert state.open_position is not None
        from janus.strategies.base import Signal
        return Order(
            strategy_id=self.id,
            symbol=state.symbol,
            side=Side.LONG,                 # closes a long via opposing-side order at execution layer
            intent=OrderIntent.CLOSE,
            qty=state.open_position.qty,
            order_type=OrderType.MARKET,
            signal=Signal(
                name=f"refractory.exit.{reason}",
                confidence=1.0,
                features={"last_price": float(state.last_price)},
                note=reason,
            ),
        )
