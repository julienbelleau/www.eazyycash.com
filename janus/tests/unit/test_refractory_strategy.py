"""Refractory strategy state-machine tests.

These pin the state transitions: IDLE → IN_CASCADE → IN_TRADE → COOLDOWN → IDLE.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from janus.features.refractory_features import MarketWindow
from janus.strategies.base import MarketState, OrderIntent, Position, Side
from janus.strategies.refractory.signals import CascadeThresholds, ExhaustionThresholds
from janus.strategies.refractory.strategy import (
    ExitConfig,
    RefractoryConfig,
    RefractoryStrategy,
    State,
)


def _bar(ts: datetime, close: float, vol: float = 50.0) -> dict[str, object]:
    return {
        "ts": ts,
        "open": Decimal(str(close)),
        "high": Decimal(str(close + 5)),
        "low": Decimal(str(close - 5)),
        "close": Decimal(str(close)),
        "volume": Decimal(str(vol)),
        "quote_volume": Decimal(str(vol * close)),
        "trade_count": 100,
        "taker_buy_volume": Decimal(str(vol / 2)),
        "taker_buy_quote_volume": Decimal(str((vol / 2) * close)),
    }


def _liq(ts: datetime, notional: float) -> dict[str, object]:
    return {"ts": ts, "side": "long", "price": Decimal("40000"),
            "quantity": Decimal("1"), "notional_usd": Decimal(str(notional))}


def _make_strategy() -> RefractoryStrategy:
    cfg = RefractoryConfig(
        symbol="BTCUSDT",
        cascade=CascadeThresholds(4.0, 200_000_000, 8.0, 2.0),
        exhaustion=ExhaustionThresholds(),
        exits=ExitConfig(),
        cooldown_minutes=240,
        position_size_quote=Decimal("1000"),
    )
    return RefractoryStrategy(cfg)


def _market_state(ts: datetime, price: float, window: MarketWindow,
                  baseline: list[dict[str, object]],
                  position: Position | None = None) -> MarketState:
    return MarketState(
        as_of=ts, symbol="BTCUSDT", last_price=Decimal(str(price)),
        open_position=position,
        extras={"window": window, "baseline_bars": baseline},
    )


@pytest.mark.asyncio()
async def test_starts_idle() -> None:
    s = _make_strategy()
    assert s.state is State.IDLE


@pytest.mark.asyncio()
async def test_idle_transitions_to_cascade_on_signal() -> None:
    s = _make_strategy()
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    bars = [_bar(ts - timedelta(minutes=60 - i), 40_000 - i * 33, vol=60.0) for i in range(60)]
    baseline = [_bar(ts - timedelta(days=d), 40_000, vol=20.0) for d in range(30)]
    liqs = [_liq(ts - timedelta(minutes=i), 5_000_000) for i in range(60)]
    w = MarketWindow(
        as_of=ts, bars=bars, liquidations=liqs,
        open_interest=[
            {"ts": bars[0]["ts"], "oi_contracts": Decimal("100000")},
            {"ts": ts, "oi_contracts": Decimal("90000")},
        ],
        funding_history=[],
    )
    orders = await s.on_tick(_market_state(ts, 38_000, w, baseline))
    assert orders == []
    assert s.state is State.IN_CASCADE


@pytest.mark.asyncio()
async def test_idle_stays_idle_when_no_signal() -> None:
    s = _make_strategy()
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    calm_bars = [_bar(ts - timedelta(minutes=i), 40_000) for i in range(60, 0, -1)]
    baseline = [_bar(ts - timedelta(days=d), 40_000, vol=20.0) for d in range(30)]
    w = MarketWindow(as_of=ts, bars=calm_bars, liquidations=[], open_interest=[], funding_history=[])
    orders = await s.on_tick(_market_state(ts, 40_000, w, baseline))
    assert orders == []
    assert s.state is State.IDLE


@pytest.mark.asyncio()
async def test_stop_loss_exit_emits_close_order() -> None:
    s = _make_strategy()
    s.state = State.IN_TRADE
    from janus.strategies.refractory.strategy import _CascadeContext
    s._ctx = _CascadeContext(
        started_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        pre_cascade_price=Decimal("40000"),
        pre_cascade_oi=Decimal("100000"),
        cascade_low_price=Decimal("38000"),
        entry_price=Decimal("38500"),
        entry_ts=datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
        high_water_mark=Decimal("38500"),
    )
    ts = datetime(2024, 1, 1, 13, 5, tzinfo=timezone.utc)
    pos = Position(
        symbol="BTCUSDT", side=Side.LONG, qty=Decimal("0.025"),
        avg_entry_price=Decimal("38500"), opened_at=s._ctx.entry_ts,
        strategy_id=s.id,
        stop_loss=Decimal("37730"),     # 2% under entry
    )
    w = MarketWindow(as_of=ts, bars=[_bar(ts, 37_500)], liquidations=[],
                     open_interest=[{"ts": ts, "oi_contracts": Decimal("90000")}],
                     funding_history=[])
    state = _market_state(ts, 37_500, w, [], position=pos)  # below SL
    orders = await s.on_tick(state)
    assert len(orders) == 1
    assert orders[0].intent is OrderIntent.CLOSE
    assert orders[0].signal is not None
    assert orders[0].signal.name == "refractory.exit.stop_loss"
    assert s.state is State.COOLDOWN


@pytest.mark.asyncio()
async def test_time_stop_triggers_after_horizon() -> None:
    s = _make_strategy()
    s.state = State.IN_TRADE
    from janus.strategies.refractory.strategy import _CascadeContext
    entry_ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    s._ctx = _CascadeContext(
        started_at=entry_ts,
        pre_cascade_price=Decimal("40000"),
        pre_cascade_oi=Decimal("100000"),
        cascade_low_price=Decimal("38000"),
        entry_price=Decimal("38500"),
        entry_ts=entry_ts,
        high_water_mark=Decimal("38600"),
    )
    ts = entry_ts + timedelta(hours=24, minutes=1)  # past time stop
    pos = Position(symbol="BTCUSDT", side=Side.LONG, qty=Decimal("0.025"),
                   avg_entry_price=Decimal("38500"), opened_at=entry_ts,
                   strategy_id=s.id, stop_loss=Decimal("37730"))
    w = MarketWindow(as_of=ts, bars=[_bar(ts, 38_700)], liquidations=[],
                     open_interest=[{"ts": ts, "oi_contracts": Decimal("90000")}],
                     funding_history=[])
    orders = await s.on_tick(_market_state(ts, 38_700, w, [], position=pos))
    assert len(orders) == 1
    assert orders[0].signal is not None
    assert "time_stop" in orders[0].signal.name


@pytest.mark.asyncio()
async def test_cooldown_prevents_re_entry_until_expired() -> None:
    s = _make_strategy()
    s.state = State.COOLDOWN
    s._cooldown_until = datetime(2024, 1, 1, 16, 0, tzinfo=timezone.utc)
    ts_in_cd = datetime(2024, 1, 1, 14, 0, tzinfo=timezone.utc)

    w = MarketWindow(as_of=ts_in_cd, bars=[_bar(ts_in_cd, 40_000)],
                     liquidations=[], open_interest=[], funding_history=[])
    orders = await s.on_tick(_market_state(ts_in_cd, 40_000, w, []))
    assert orders == []
    assert s.state is State.COOLDOWN

    ts_after = datetime(2024, 1, 1, 16, 1, tzinfo=timezone.utc)
    w2 = MarketWindow(as_of=ts_after, bars=[_bar(ts_after, 40_000)],
                      liquidations=[], open_interest=[], funding_history=[])
    await s.on_tick(_market_state(ts_after, 40_000, w2, []))
    assert s.state is State.IDLE
