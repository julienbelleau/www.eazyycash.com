"""Stablecoin Stress Flow strategy.

States:
  IDLE             — scanning for stress events
  STRESS_PENDING   — stress detected; waiting up to 45 min for flow confirmation
  IN_TRADE         — long BTC spot; managing fast exits
  COOLDOWN         — 6h pause after exit (avoid re-firing on the same event)

Per the plan §6:
- Long BTC SPOT (NEVER perps — we capture physical flow, not leverage).
- Sizing: 5-10% of portfolio, inversely proportional to current BTC vol
  (`vol_inverse_sizing` flag).
- Exits: TP +1.5% to +3%, SL -1%, time stop 6h.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

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
    IDLE = "idle"
    STRESS_PENDING = "stress_pending"
    IN_TRADE = "in_trade"
    COOLDOWN = "cooldown"


@dataclass(frozen=True, slots=True)
class StablecoinExitConfig:
    take_profit_pct_low: float = 1.5
    take_profit_pct_high: float = 3.0
    stop_loss_pct: float = -1.0
    time_stop_hours: int = 6


@dataclass(frozen=True, slots=True)
class StablecoinStrategyConfig:
    base_position_pct: float = 7.5
    vol_inverse_sizing: bool = True
    max_pct_of_portfolio: float = 10.0
    min_pct_of_portfolio: float = 1.0
    max_delay_min_after_stress: int = 45
    cooldown_hours: int = 6
    exits: StablecoinExitConfig = field(default_factory=StablecoinExitConfig)


@dataclass
class _TradeContext:
    stress_detected_at: datetime
    flow_confirmed_at: datetime | None = None
    entry_price: Decimal | None = None
    entry_ts: datetime | None = None


class StablecoinStressStrategy(StrategyBase):
    id = "stablecoin_stress_v1"

    def __init__(self, cfg: StablecoinStrategyConfig):
        self.cfg = cfg
        self.state: State = State.IDLE
        self._ctx: _TradeContext | None = None
        self._cooldown_until: datetime | None = None

    async def on_tick(self, state: MarketState) -> list[Order]:
        if self.state is State.COOLDOWN and self._cooldown_until is not None:
            if state.as_of >= self._cooldown_until:
                self.state = State.IDLE
                self._cooldown_until = None

        stress: Signal | None = state.extras.get("stress_signal")
        flow: Signal | None = state.extras.get("flow_signal")

        if self.state is State.IDLE and stress is not None:
            self._ctx = _TradeContext(stress_detected_at=state.as_of)
            self.state = State.STRESS_PENDING
            return []

        if self.state is State.STRESS_PENDING and self._ctx is not None:
            elapsed = (state.as_of - self._ctx.stress_detected_at).total_seconds() / 60.0
            if elapsed > self.cfg.max_delay_min_after_stress:
                # Trade is stale — abandon, return to idle.
                self.state = State.IDLE
                self._ctx = None
                return []
            if flow is None:
                return []

            # Compute size: vol-inverse if configured.
            vol_24h: float = state.extras.get("btc_vol_24h", 0.02)  # fraction
            pct = self.cfg.base_position_pct
            if self.cfg.vol_inverse_sizing and vol_24h > 0:
                # Reference vol = 2%; lower vol → bigger size.
                pct = self.cfg.base_position_pct * 0.02 / max(vol_24h, 0.005)
            pct = max(self.cfg.min_pct_of_portfolio, min(self.cfg.max_pct_of_portfolio, pct))

            portfolio_quote: Decimal = state.extras.get("portfolio_quote", Decimal("100000"))
            notional = portfolio_quote * Decimal(str(pct / 100.0))
            qty = notional / state.last_price if state.last_price > 0 else Decimal(0)
            if qty <= 0:
                return []

            self._ctx.flow_confirmed_at = state.as_of
            self._ctx.entry_price = state.last_price
            self._ctx.entry_ts = state.as_of
            self.state = State.IN_TRADE

            return [Order(
                strategy_id=self.id, symbol=state.symbol,
                side=Side.LONG, intent=OrderIntent.OPEN,
                qty=qty, order_type=OrderType.MARKET,
                stop_loss=state.last_price * (Decimal(1) + Decimal(str(self.cfg.exits.stop_loss_pct / 100.0))),
                signal=flow,
            )]

        if self.state is State.IN_TRADE and self._ctx is not None and state.open_position is not None:
            return self._manage_exit(state)

        return []

    def _manage_exit(self, state: MarketState) -> list[Order]:
        assert self._ctx is not None and self._ctx.entry_price is not None and self._ctx.entry_ts is not None
        ctx = self._ctx
        cfg = self.cfg.exits
        ret_pct = float((state.last_price - ctx.entry_price) / ctx.entry_price * Decimal(100))
        elapsed_h = (state.as_of - ctx.entry_ts).total_seconds() / 3600.0

        reason: str | None = None
        # Two-tiered TP: take a piece at low band, the rest at high band. v1
        # exits the entire position at the low band — staged exit lands later.
        if ret_pct >= cfg.take_profit_pct_low:
            reason = "take_profit"
        elif ret_pct <= cfg.stop_loss_pct:
            reason = "stop_loss"
        elif elapsed_h >= cfg.time_stop_hours:
            reason = "time_stop"

        if reason is None:
            return []

        assert state.open_position is not None
        order = Order(
            strategy_id=self.id, symbol=state.symbol,
            side=Side.LONG, intent=OrderIntent.CLOSE,
            qty=state.open_position.qty, order_type=OrderType.MARKET,
            signal=Signal(
                name=f"stablecoin.exit.{reason}",
                confidence=1.0,
                features={"ret_pct": ret_pct, "elapsed_h": elapsed_h},
                note=reason,
            ),
        )
        self.state = State.COOLDOWN
        self._cooldown_until = state.as_of + timedelta(hours=self.cfg.cooldown_hours)
        self._ctx = None
        return [order]
