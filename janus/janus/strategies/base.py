"""Strategy primitives + base ABC.

Every Janus strategy implements one method: `on_tick(market_state) -> list[Order]`.

The contract is intentionally minimal so strategies can be backtested and
live-traded by the same engine. The engine owns time, position state, and
P&L attribution; the strategy owns *signal logic only*.

Why so minimal:
- Easier to property-test: a strategy is a pure function of state -> orders.
- Easier to swap: regime gating lives at the engine layer, not inside strategies.
- Easier to attribute: every order carries a `strategy_id` + `signal` payload.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class Side(StrEnum):
    LONG = "long"
    SHORT = "short"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderIntent(StrEnum):
    OPEN = "open"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class Signal:
    """A strategy emits a signal explaining *why* it wants to trade.

    The signal is logged with the trade so any P&L is attributable to a feature
    snapshot — required by the "every trade explainable post-hoc" invariant.
    """

    name: str                         # e.g. "refractory.cascade_exhaustion"
    confidence: float                 # in [0, 1]
    features: dict[str, float]        # snapshot of decision-time feature values
    note: str = ""                    # short human-readable summary

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class Order:
    strategy_id: str
    symbol: str
    side: Side
    intent: OrderIntent
    qty: Decimal
    order_type: OrderType
    limit_price: Decimal | None = None
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    time_in_force_s: int | None = None    # None = GTC
    signal: Signal | None = None
    client_order_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    side: Side
    qty: Decimal
    avg_entry_price: Decimal
    opened_at: datetime
    strategy_id: str
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None

    def unrealized_pnl(self, mark: Decimal) -> Decimal:
        if self.side is Side.LONG:
            return (mark - self.avg_entry_price) * self.qty
        return (self.avg_entry_price - mark) * self.qty


@dataclass(slots=True)
class MarketState:
    """The packet a strategy sees on every tick.

    The engine populates this from the repository (point-in-time bars,
    funding, OI, recent liquidations). Strategies must not access the DB
    directly — the engine guarantees `as_of` discipline upstream.
    """

    as_of: datetime
    symbol: str
    last_price: Decimal
    open_position: Position | None
    extras: dict[str, Any] = field(default_factory=dict)


class StrategyBase(abc.ABC):
    """All strategies inherit from this. Override `on_tick` and `id`."""

    id: str

    @abc.abstractmethod
    async def on_tick(self, state: MarketState) -> list[Order]:
        """Return zero or more orders to submit. Pure function of `state`."""

    async def on_fill(self, position: Position) -> None:
        """Optional: react to a fill (e.g. reset internal cooldown)."""

    async def on_close(self, closed_position: Position, realized_pnl: Decimal) -> None:
        """Optional: react to a position closing."""
