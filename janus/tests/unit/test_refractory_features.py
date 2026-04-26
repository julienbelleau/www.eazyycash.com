"""Refractory feature module: numerical correctness on synthetic windows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from janus.features.refractory_features import (
    MarketWindow,
    cumulative_volume_delta,
    funding_zscore,
    liq_total_window,
    liq_velocity,
    oi_change_pct,
    order_flow_imbalance,
    price_drop_pct,
    volume_ratio,
)


def _bar(ts: datetime, close: float, taker_buy: float = 5.0, vol: float = 10.0) -> dict[str, object]:
    return {
        "ts": ts,
        "open": Decimal(str(close)),
        "high": Decimal(str(close + 10)),
        "low": Decimal(str(close - 10)),
        "close": Decimal(str(close)),
        "volume": Decimal(str(vol)),
        "quote_volume": Decimal(str(vol * close)),
        "trade_count": 100,
        "taker_buy_volume": Decimal(str(taker_buy)),
        "taker_buy_quote_volume": Decimal(str(taker_buy * close)),
    }


def _liq(ts: datetime, notional: float, side: str = "long") -> dict[str, object]:
    return {
        "ts": ts, "side": side,
        "price": Decimal("40000"),
        "quantity": Decimal("1"),
        "notional_usd": Decimal(str(notional)),
    }


def test_liq_total_window() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    w = MarketWindow(
        as_of=ts, bars=[], open_interest=[], funding_history=[],
        liquidations=[_liq(ts, 100_000), _liq(ts, 50_000), _liq(ts, 25_000)],
    )
    assert liq_total_window(w) == 175_000.0


def test_liq_velocity_recent_minus_prior() -> None:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    liqs = [
        _liq(now - timedelta(minutes=1), 100_000),    # latest bucket
        _liq(now - timedelta(minutes=2), 200_000),    # latest bucket
        _liq(now - timedelta(minutes=6), 50_000),     # prior bucket
    ]
    w = MarketWindow(as_of=now, bars=[], open_interest=[], funding_history=[], liquidations=liqs)
    # latest = 300000, prior = 50000 → velocity = 250000
    assert liq_velocity(w, bucket_minutes=5) == 250_000.0


def test_price_drop_pct_negative_when_price_rises() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    w = MarketWindow(
        as_of=ts,
        bars=[_bar(ts, 40_000), _bar(ts, 41_000)],
        open_interest=[], funding_history=[], liquidations=[],
    )
    # 40000 -> 41000 = -2.5% drop
    assert price_drop_pct(w) < 0


def test_price_drop_pct_positive_when_price_falls() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    w = MarketWindow(
        as_of=ts,
        bars=[_bar(ts, 40_000), _bar(ts, 38_000)],
        open_interest=[], funding_history=[], liquidations=[],
    )
    assert abs(price_drop_pct(w) - 5.0) < 1e-6


def test_oi_change_pct() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    w = MarketWindow(
        as_of=ts, bars=[], liquidations=[], funding_history=[],
        open_interest=[
            {"ts": ts, "oi_contracts": Decimal("100000")},
            {"ts": ts, "oi_contracts": Decimal("90000")},
        ],
    )
    # OI dropped 10% — expect -10.
    assert oi_change_pct(w) == -10.0


def test_volume_ratio() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(ts, 40_000, vol=20.0) for _ in range(60)]   # window
    baseline = [_bar(ts, 40_000, vol=10.0) for _ in range(60)]  # baseline
    w = MarketWindow(as_of=ts, bars=bars, open_interest=[], funding_history=[], liquidations=[])
    # window has 60 bars * 20 = 1200; baseline mean 10 → scaled = 10*60 = 600 → ratio = 2.0.
    assert abs(volume_ratio(w, baseline_bars=baseline) - 2.0) < 1e-9


def test_funding_zscore_zero_for_constant_history() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    w = MarketWindow(
        as_of=ts, bars=[], liquidations=[], open_interest=[],
        funding_history=[{"rate": Decimal("0.0001")} for _ in range(30)],
    )
    assert funding_zscore(w) == 0.0


def test_order_flow_imbalance() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # All taker buys → OFI = +1
    w_buy = MarketWindow(
        as_of=ts, bars=[_bar(ts, 40_000, taker_buy=10.0, vol=10.0)],
        open_interest=[], funding_history=[], liquidations=[],
    )
    assert order_flow_imbalance(w_buy) == 1.0
    # All taker sells → OFI = -1
    w_sell = MarketWindow(
        as_of=ts, bars=[_bar(ts, 40_000, taker_buy=0.0, vol=10.0)],
        open_interest=[], funding_history=[], liquidations=[],
    )
    assert order_flow_imbalance(w_sell) == -1.0


def test_cvd_zero_when_balanced() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # taker_buy_quote = 5*40000 = 200000; total quote = 10*40000 = 400000; sell = 200000.
    w = MarketWindow(
        as_of=ts, bars=[_bar(ts, 40_000, taker_buy=5.0, vol=10.0)],
        open_interest=[], funding_history=[], liquidations=[],
    )
    assert cumulative_volume_delta(w) == 0.0
