"""Refractory cascade + exhaustion signal tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np

from janus.features.refractory_features import MarketWindow
from janus.strategies.refractory.signals import (
    CascadeDetector,
    CascadeThresholds,
    ExhaustionDetector,
    ExhaustionThresholds,
    contagion_multiplier,
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


def test_cascade_not_detected_in_calm_market() -> None:
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    bars = [_bar(ts - timedelta(minutes=i), 40_000) for i in range(60, 0, -1)]
    baseline = [_bar(ts - timedelta(days=d), 40_000, vol=20.0) for d in range(30)]
    w = MarketWindow(
        as_of=ts, bars=bars, liquidations=[],
        open_interest=[
            {"ts": bars[0]["ts"], "oi_contracts": Decimal("100000")},
            {"ts": ts, "oi_contracts": Decimal("100000")},
        ],
        funding_history=[],
    )
    cd = CascadeDetector("BTCUSDT", CascadeThresholds(4.0, 200_000_000, 8.0, 2.0))
    assert cd.evaluate(w, baseline) is None


def test_cascade_detected_under_textbook_conditions() -> None:
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Price drops 5%, volume 3× baseline, OI -10%, $300M liquidations.
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
    cd = CascadeDetector("BTCUSDT", CascadeThresholds(4.0, 200_000_000, 8.0, 2.0))
    sig = cd.evaluate(w, baseline)
    assert sig is not None
    assert sig.name == "refractory.cascade_detected"
    assert 0.0 < sig.confidence <= 1.0


def test_adaptive_threshold_floats_with_market() -> None:
    cd = CascadeDetector("BTCUSDT", CascadeThresholds(4.0, 100_000_000, 8.0, 2.0), min_warmup=50)
    rng = np.random.default_rng(0)
    # Feed a stream where 95th percentile lands far above the nominal floor.
    for x in rng.uniform(50_000_000, 800_000_000, size=400):
        cd.update_thresholds(float(x))
    assert (cd.liq_quantile.threshold() or 0) > 100_000_000


def test_exhaustion_requires_all_conditions() -> None:
    """Exhaustion should NOT fire if BOCPD doesn't see a CP yet."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    ed = ExhaustionDetector("BTCUSDT", ExhaustionThresholds())
    # Very long stable cascade window — BOCPD MAP RL will be large.
    for i in range(300):
        w = MarketWindow(
            as_of=ts + timedelta(minutes=i),
            bars=[_bar(ts + timedelta(minutes=i), 40_000)],
            liquidations=[_liq(ts + timedelta(minutes=i), 5_000_000)],
            open_interest=[], funding_history=[],
        )
        ed.update(w)
    sig = ed.evaluate(MarketWindow(
        as_of=ts + timedelta(minutes=400),
        bars=[_bar(ts + timedelta(minutes=400), 40_000)],
        liquidations=[],
        open_interest=[], funding_history=[],
    ))
    # No exhaustion: with no recent CP, RL is far above the threshold.
    assert sig is None


def test_contagion_multiplier_grows_with_coincident_drops() -> None:
    assert contagion_multiplier({"BTC": 5.0}) == 1.25
    assert contagion_multiplier({"BTC": 5.0, "ETH": 5.0}) == 1.5
    assert contagion_multiplier({"BTC": 5.0, "ETH": 5.0, "SOL": 5.0}) == 1.75
    assert contagion_multiplier({"BTC": 5.0, "ETH": 5.0, "SOL": 5.0, "ADA": 5.0}) == 2.0
    # Capped at 2.0
    assert contagion_multiplier({f"X{i}": 5.0 for i in range(10)}) == 2.0
    # No drops → multiplier = 1.0
    assert contagion_multiplier({"BTC": 0.5}) == 1.0
