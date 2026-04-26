"""Narrative rotation strategy state machine tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from janus.strategies.base import MarketState, OrderIntent, Side, Signal
from janus.strategies.narrative_rotation.strategy import (
    NarrativeExitConfig,
    NarrativeRotationStrategy,
    NarrativeStrategyConfig,
    State,
)


def _make() -> NarrativeRotationStrategy:
    cfg = NarrativeStrategyConfig(
        positions_per_basket=3, pct_per_ticker=4.0, fees_taker_pct=0.10,
        cooldown_days=14,
        exits=NarrativeExitConfig(),
    )
    return NarrativeRotationStrategy(cfg)


def _state(**extras: object) -> MarketState:
    return MarketState(
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="BASKET", last_price=Decimal("1"),
        open_position=None, extras=extras,
    )


@pytest.mark.asyncio()
async def test_no_signal_no_orders() -> None:
    s = _make()
    orders = await s.on_tick(_state())
    assert orders == []
    assert s.state is State.WATCHING


@pytest.mark.asyncio()
async def test_emergent_signal_opens_basket() -> None:
    s = _make()
    sig = Signal(name="narrative.emergent", confidence=0.7, features={"acceleration": 0.001})
    orders = await s.on_tick(_state(
        emergent_signal=sig,
        emergent_narrative="ai",
        emergent_tickers=["AAA", "BBB", "CCC", "DDD"],
        portfolio_quote=Decimal("100000"),
        marks={"AAA": Decimal("100"), "BBB": Decimal("50"), "CCC": Decimal("10"), "DDD": Decimal("1")},
    ))
    assert s.state is State.HOLDING_BASKET
    # 3 tickers (top of cfg.positions_per_basket); each at 4% of 100k = 4k
    assert len(orders) == 3
    for o in orders:
        assert o.intent is OrderIntent.OPEN
        assert o.side is Side.LONG


@pytest.mark.asyncio()
async def test_basket_take_profit_closes_all() -> None:
    s = _make()
    # Forcibly seed HOLDING state.
    sig = Signal(name="narrative.emergent", confidence=0.7, features={})
    await s.on_tick(_state(
        emergent_signal=sig, emergent_narrative="ai",
        emergent_tickers=["AAA", "BBB", "CCC"],
        portfolio_quote=Decimal("100000"),
        marks={"AAA": Decimal("100"), "BBB": Decimal("50"), "CCC": Decimal("10")},
    ))
    # 3 days later, basket up 50% → TP triggers.
    later = datetime(2024, 1, 4, tzinfo=timezone.utc)
    state = MarketState(
        as_of=later, symbol="BASKET", last_price=Decimal("1"),
        open_position=None,
        extras={
            "basket_value": Decimal("18000"),       # entry was 12000 (3 * 4000)
            "marks": {"AAA": Decimal("150"), "BBB": Decimal("75"), "CCC": Decimal("15")},
            "basket_positions": {"AAA": Decimal("40"), "BBB": Decimal("80"), "CCC": Decimal("400")},
        },
    )
    orders = await s.on_tick(state)
    assert s.state is State.COOLDOWN
    assert len(orders) == 3
    assert all(o.intent is OrderIntent.CLOSE for o in orders)
    assert all(o.signal is not None and "take_profit" in o.signal.name for o in orders)


@pytest.mark.asyncio()
async def test_basket_stop_loss() -> None:
    s = _make()
    sig = Signal(name="narrative.emergent", confidence=0.7, features={})
    await s.on_tick(_state(
        emergent_signal=sig, emergent_narrative="ai",
        emergent_tickers=["AAA"],
        portfolio_quote=Decimal("100000"),
        marks={"AAA": Decimal("100")},
    ))
    later = datetime(2024, 1, 5, tzinfo=timezone.utc)
    state = MarketState(
        as_of=later, symbol="BASKET", last_price=Decimal("1"),
        open_position=None,
        extras={
            # entry was 4000; -20% → 3200 → triggers -15% SL
            "basket_value": Decimal("3200"),
            "marks": {"AAA": Decimal("80")},
            "basket_positions": {"AAA": Decimal("40")},
        },
    )
    orders = await s.on_tick(state)
    assert s.state is State.COOLDOWN
    assert len(orders) == 1
    assert "stop_loss" in orders[0].signal.name
