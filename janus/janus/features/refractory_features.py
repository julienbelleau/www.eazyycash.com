"""Refractory-period features (point-in-time).

All features take a `MarketWindow` containing only data with `ts <= as_of`.
The repository layer guarantees this; the functions here are pure and
deterministic.

Features computed:
- liq_total_window — sum of USD liquidations in the lookback
- liq_velocity — d/dt of liquidations (current vs prior bar)
- price_drop_pct — (start_price - last_price) / start_price * 100
- oi_change_pct — % change in open interest over the window
- volume_ratio — window volume / 30d SMA volume
- funding_zscore — z-score of current funding vs trailing 30d
- ofi — order flow imbalance (taker_buy_volume - taker_sell_volume) / volume
- cvd — cumulative volume delta over the window

The features map 1:1 to the signals layer (`refractory.signals`); separating
features from signals keeps the math testable in isolation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from math import sqrt
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketWindow:
    """Bag of point-in-time series passed to the feature functions."""

    as_of: datetime
    bars: Sequence[dict[str, Any]]                      # OHLCV with taker_buy_volume
    liquidations: Sequence[dict[str, Any]]              # tuples within the window
    open_interest: Sequence[dict[str, Any]]             # OI snapshots
    funding_history: Sequence[dict[str, Any]]           # >=30d of recent funding rates


def liq_total_window(window: MarketWindow) -> float:
    return float(sum(Decimal(str(r["notional_usd"])) for r in window.liquidations))


def liq_velocity(window: MarketWindow, *, bucket_minutes: int = 5) -> float:
    """Delta of liquidation USD between the latest bucket and the prior bucket."""
    if not window.liquidations:
        return 0.0
    cutoff = window.as_of
    bucket = bucket_minutes * 60.0
    latest = 0.0
    prior = 0.0
    for r in window.liquidations:
        delta_s = (cutoff - r["ts"]).total_seconds()
        if 0 <= delta_s < bucket:
            latest += float(r["notional_usd"])
        elif bucket <= delta_s < 2 * bucket:
            prior += float(r["notional_usd"])
    return latest - prior


def price_drop_pct(window: MarketWindow) -> float:
    if len(window.bars) < 2:
        return 0.0
    start = float(window.bars[0]["close"])
    end = float(window.bars[-1]["close"])
    if start == 0:
        return 0.0
    return (start - end) / start * 100.0


def oi_change_pct(window: MarketWindow) -> float:
    if len(window.open_interest) < 2:
        return 0.0
    start = float(window.open_interest[0]["oi_contracts"])
    end = float(window.open_interest[-1]["oi_contracts"])
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def volume_ratio(window: MarketWindow, *, baseline_bars: Sequence[dict[str, Any]]) -> float:
    """Window volume / mean volume of `baseline_bars` (typically 30d of bars)."""
    if not window.bars or not baseline_bars:
        return 0.0
    window_v = sum(float(b["volume"]) for b in window.bars)
    baseline_v = sum(float(b["volume"]) for b in baseline_bars) / len(baseline_bars)
    if baseline_v == 0:
        return 0.0
    # Window covers len(window.bars) minutes; rescale baseline to the same horizon.
    scaled_baseline = baseline_v * len(window.bars)
    return window_v / scaled_baseline


def funding_zscore(window: MarketWindow) -> float:
    rates = [float(r["rate"]) for r in window.funding_history]
    if len(rates) < 5:
        return 0.0
    mean = sum(rates[:-1]) / max(len(rates) - 1, 1)
    var = sum((r - mean) ** 2 for r in rates[:-1]) / max(len(rates) - 1, 1)
    sd = sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return 0.0
    return (rates[-1] - mean) / sd


def order_flow_imbalance(window: MarketWindow) -> float:
    """OFI = (taker_buy_volume - taker_sell_volume) / volume, in [-1, 1].

    Liquidation cascades show extreme negative OFI; exhaustion shows it reverting
    toward zero. Used by the exhaustion-confirmation signal (UPGRADES §1.2).
    """
    total_v = sum(float(b["volume"]) for b in window.bars)
    if total_v == 0:
        return 0.0
    taker_buy = sum(float(b["taker_buy_volume"]) for b in window.bars)
    taker_sell = total_v - taker_buy
    return (taker_buy - taker_sell) / total_v


def cumulative_volume_delta(window: MarketWindow) -> float:
    """CVD over the window (signed flow). Returns USD."""
    cvd = 0.0
    for b in window.bars:
        v = float(b["volume"])
        tb = float(b["taker_buy_volume"])
        ts_q = float(b["taker_buy_quote_volume"])
        # Approximate sell quote vol from totals.
        total_quote = float(b["quote_volume"])
        sell_quote = total_quote - ts_q
        cvd += ts_q - sell_quote
        # `v` participates only via OFI; CVD is in quote (USD) terms.
        _ = (v, tb)
    return cvd
