"""Stablecoin signal + strategy state machine tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from janus.features.stablecoin_features import StablecoinSnapshot
from janus.strategies.base import MarketState, OrderIntent, Position, Side, Signal
from janus.strategies.stablecoin_stress.signals import (
    FlowParams,
    StressParams,
    detect_flow_signal,
    detect_stress_event,
)
from janus.strategies.stablecoin_stress.strategy import (
    StablecoinExitConfig,
    StablecoinStrategyConfig,
    StablecoinStressStrategy,
    State,
)


def _snap(**kw: object) -> StablecoinSnapshot:
    base = dict(
        asset="USDC", as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        cex_price_usd=Decimal("1.0"), dex_price_usd=Decimal("1.0"),
        pool_depth_usd=Decimal("500000000"),
        issuer_cash_equivalents_usd=Decimal("103000000000"),
        issuer_total_liabilities_usd=Decimal("100000000000"),
        cex_volume_24h_usd=Decimal("100000000"),
        cex_volume_24h_baseline=Decimal("80000000"),
        btc_exchange_inflow_btc=Decimal("100"),
        btc_exchange_inflow_baseline=Decimal("80"),
        btc_pair_volume_btcusdt=Decimal("60"),
        btc_pair_volume_btcusdc=Decimal("40"),
        funding_1h=Decimal("0.0001"),
        funding_8h=Decimal("0.00012"),
        funding_24h=Decimal("0.00014"),
    )
    base.update(kw)
    return StablecoinSnapshot(**base)  # type: ignore[arg-type]


def test_no_stress_at_peg() -> None:
    assert detect_stress_event(_snap()) is None


def test_stress_when_depeg_and_volume_anomaly() -> None:
    snap = _snap(dex_price_usd=Decimal("0.997"),
                 cex_volume_24h_usd=Decimal("200000000"))  # 2.5× baseline
    sig = detect_stress_event(snap)
    assert sig is not None
    assert "USDC" in (sig.note or "")


def test_no_flow_signal_when_inflow_normal() -> None:
    assert detect_flow_signal(_snap()) is None


def test_flow_signal_fires_when_inflow_up() -> None:
    snap = _snap(
        btc_exchange_inflow_btc=Decimal("130"),  # 1.625× baseline
        btc_pair_volume_btcusdt=Decimal("80"),
        btc_pair_volume_btcusdc=Decimal("20"),
    )
    sig = detect_flow_signal(snap)
    assert sig is not None
    assert sig.features["btc_inflow_ratio"] > 1.3


def test_flow_signal_blocked_when_funding_priced() -> None:
    snap = _snap(
        btc_exchange_inflow_btc=Decimal("130"),
        btc_pair_volume_btcusdt=Decimal("80"), btc_pair_volume_btcusdc=Decimal("20"),
        funding_1h=Decimal("0.0001"), funding_8h=Decimal("0.001"), funding_24h=Decimal("0.002"),
    )
    assert detect_flow_signal(snap) is None


# ─── strategy state machine ───

def _make() -> StablecoinStressStrategy:
    return StablecoinStressStrategy(StablecoinStrategyConfig(
        base_position_pct=7.5,
        vol_inverse_sizing=False,
        max_delay_min_after_stress=45,
        cooldown_hours=6,
        exits=StablecoinExitConfig(),
    ))


def _state(ts: datetime, price: float, **extras: object) -> MarketState:
    return MarketState(
        as_of=ts, symbol="BTCUSDT", last_price=Decimal(str(price)),
        open_position=None, extras=extras,
    )


@pytest.mark.asyncio()
async def test_idle_to_pending_on_stress() -> None:
    s = _make()
    sig = Signal(name="stablecoin.stress_event", confidence=0.5, features={})
    await s.on_tick(_state(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                            40_000, stress_signal=sig))
    assert s.state is State.STRESS_PENDING


@pytest.mark.asyncio()
async def test_pending_times_out() -> None:
    s = _make()
    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    sig_stress = Signal(name="stablecoin.stress_event", confidence=0.5, features={})
    await s.on_tick(_state(base, 40_000, stress_signal=sig_stress))
    # 50 minutes later, no flow → revert to IDLE
    await s.on_tick(_state(base + timedelta(minutes=50), 40_000))
    assert s.state is State.IDLE


@pytest.mark.asyncio()
async def test_flow_confirmation_opens_position() -> None:
    s = _make()
    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    stress_sig = Signal(name="stablecoin.stress_event", confidence=0.5, features={})
    flow_sig = Signal(name="stablecoin.flow_signal", confidence=0.7, features={})
    await s.on_tick(_state(base, 40_000, stress_signal=stress_sig))
    orders = await s.on_tick(_state(
        base + timedelta(minutes=20), 40_000,
        flow_signal=flow_sig, btc_vol_24h=0.02,
        portfolio_quote=Decimal("100000"),
    ))
    assert s.state is State.IN_TRADE
    assert len(orders) == 1
    assert orders[0].intent is OrderIntent.OPEN
    assert orders[0].side is Side.LONG


@pytest.mark.asyncio()
async def test_take_profit_exit() -> None:
    s = _make()
    # Force IN_TRADE state.
    from janus.strategies.stablecoin_stress.strategy import _TradeContext
    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    s.state = State.IN_TRADE
    s._ctx = _TradeContext(
        stress_detected_at=base, flow_confirmed_at=base,
        entry_price=Decimal("40000"), entry_ts=base,
    )
    pos = Position(symbol="BTCUSDT", side=Side.LONG, qty=Decimal("0.1"),
                   avg_entry_price=Decimal("40000"), opened_at=base, strategy_id=s.id)
    state = MarketState(
        as_of=base + timedelta(minutes=30), symbol="BTCUSDT",
        last_price=Decimal("40700"),  # +1.75% — triggers TP at 1.5%
        open_position=pos, extras={},
    )
    orders = await s.on_tick(state)
    assert len(orders) == 1
    assert orders[0].intent is OrderIntent.CLOSE
    assert "take_profit" in orders[0].signal.name
    assert s.state is State.COOLDOWN
