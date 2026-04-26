"""Refractory-period signal layer.

Two distinct signals:
  1. Cascade detection (entry trigger arming) — fires when the market enters a
     leveraged-driven liquidation cascade.
  2. Exhaustion confirmation (entry trigger firing) — fires when the cascade
     ends and the refractory window opens.

Pro-tier upgrades vs the original plan:
  * Adaptive thresholds (UPGRADES §1.1): dollar amounts come from
    online quantiles maintained on the 90-day liquidation distribution. Falls
    back to the YAML defaults during P² warm-up.
  * OFI/CVD-based exhaustion (UPGRADES §1.2): the "price stable for 30 min"
    rule is augmented with order-flow-imbalance reversion — a much earlier
    and lower-false-positive signal.
  * Multi-asset contagion (UPGRADES §1.3): cascade strength is multiplied
    when correlated symbols (BTC + ETH + top alts) move together.
  * BOCPD on liquidation rate (UPGRADES §1.4): exhaustion confirmed when the
    BOCPD run-length posterior collapses (mean shift in liq generation).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from janus.features import refractory_features as rf
from janus.features.adaptive_thresholds import RollingQuantile
from janus.features.bocpd import Bocpd
from janus.strategies.base import Signal


# ─────────────────────────── cascade detection ───────────────────────────

@dataclass(frozen=True, slots=True)
class CascadeThresholds:
    price_drop_pct_min: float           # e.g. 4.0 for BTC
    liq_usd_min: float                  # nominal floor before the quantile takes over
    oi_drop_pct_min: float              # e.g. 8.0
    volume_ratio_min: float             # e.g. 2.0
    quantile_p: float = 0.95            # 95th percentile of trailing liq volume


class CascadeDetector:
    """Detects a cascade in a single symbol over a configurable window.

    Maintains a per-symbol P² quantile of `liq_total_window` so the dollar
    threshold floats with the market.
    """

    def __init__(self, symbol: str, thresholds: CascadeThresholds, *, min_warmup: int = 200):
        self.symbol = symbol
        self.thresholds = thresholds
        self.liq_quantile = RollingQuantile.make(thresholds.quantile_p, min_warmup=min_warmup)

    def update_thresholds(self, liq_usd_in_window: float) -> None:
        """Feed the rolling quantile a new observation. Call once per evaluation."""
        self.liq_quantile.feed(liq_usd_in_window)

    def evaluate(self, window: rf.MarketWindow, baseline_bars: Sequence[dict[str, Any]]) -> Signal | None:
        liq_total = rf.liq_total_window(window)
        # Adaptive: if the quantile is warm, use max(nominal floor, quantile).
        adaptive_floor = self.liq_quantile.threshold()
        liq_threshold = max(self.thresholds.liq_usd_min, adaptive_floor or 0.0)

        drop_pct = rf.price_drop_pct(window)
        oi_drop = -rf.oi_change_pct(window)  # cascade => OI shrinks
        vol_ratio = rf.volume_ratio(window, baseline_bars=baseline_bars)

        criteria = {
            "drop_pct": drop_pct >= self.thresholds.price_drop_pct_min,
            "liq": liq_total >= liq_threshold,
            "oi_drop": oi_drop >= self.thresholds.oi_drop_pct_min,
            "volume": vol_ratio >= self.thresholds.volume_ratio_min,
        }
        if not all(criteria.values()):
            return None

        # Confidence is the geometric mean of how much each criterion exceeds threshold.
        # Bounded to [0, 1] via tanh on the log-ratio.
        from math import log, tanh
        ratios = [
            drop_pct / max(self.thresholds.price_drop_pct_min, 1e-9),
            liq_total / max(liq_threshold, 1e-9),
            oi_drop / max(self.thresholds.oi_drop_pct_min, 1e-9),
            vol_ratio / max(self.thresholds.volume_ratio_min, 1e-9),
        ]
        gm = sum(log(max(r, 1e-9)) for r in ratios) / len(ratios)
        conf = (tanh(gm) + 1.0) / 2.0  # squash to [0, 1]

        return Signal(
            name="refractory.cascade_detected",
            confidence=conf,
            features={
                "liq_total_usd": liq_total,
                "liq_threshold_usd": liq_threshold,
                "price_drop_pct": drop_pct,
                "oi_drop_pct": oi_drop,
                "volume_ratio": vol_ratio,
            },
            note=f"cascade @{window.as_of.isoformat()} ({self.symbol})",
        )


# ─────────────────────────── exhaustion confirmation ───────────────────────────

@dataclass(frozen=True, slots=True)
class ExhaustionThresholds:
    liq_velocity_pct_of_peak_max: float = 10.0   # current/peak <= 10%
    price_stability_window_min: int = 30
    price_range_pct_max: float = 1.5
    no_new_low_window_min: int = 30
    bocpd_run_length_max: int = 8                # BOCPD MAP RL <= this => CP fresh
    ofi_reversion_threshold: float = -0.10       # OFI must rebound above this


class ExhaustionDetector:
    """Confirms cascade exhaustion via the union of multiple weak signals.

    Each component is necessary; the combination is (intentionally) conservative
    because a false exhaustion = entering before the bottom = -2% stop hit.
    """

    def __init__(self, symbol: str, thresholds: ExhaustionThresholds):
        self.symbol = symbol
        self.thresholds = thresholds
        self.bocpd = Bocpd.make(hazard_lambda=200.0)
        self._peak_liq_velocity: float = 0.0
        self._cascade_low: float | None = None
        self._cascade_low_ts: datetime | None = None

    def reset(self) -> None:
        """Call when leaving the cascade state."""
        self.bocpd = Bocpd.make(hazard_lambda=200.0)
        self._peak_liq_velocity = 0.0
        self._cascade_low = None
        self._cascade_low_ts = None

    def update(self, window: rf.MarketWindow) -> None:
        """Feed the BOCPD + track peak velocity. Call every tick during cascade."""
        v = rf.liq_velocity(window)
        if v > self._peak_liq_velocity:
            self._peak_liq_velocity = v
        # Feed BOCPD with the absolute liquidation velocity.
        self.bocpd.update(v)
        if window.bars:
            last_close = float(window.bars[-1]["close"])
            if self._cascade_low is None or last_close < self._cascade_low:
                self._cascade_low = last_close
                self._cascade_low_ts = window.as_of

    def evaluate(self, window: rf.MarketWindow) -> Signal | None:
        if not window.bars:
            return None

        # 1. Liquidation velocity has decayed below the peak fraction.
        cur_v = rf.liq_velocity(window)
        if self._peak_liq_velocity <= 0:
            return None
        velocity_ratio_pct = (cur_v / self._peak_liq_velocity) * 100.0
        if velocity_ratio_pct > self.thresholds.liq_velocity_pct_of_peak_max:
            return None

        # 2. BOCPD says the most-likely run-length is small (recent CP).
        rl = self.bocpd.run_length_map
        if rl > self.thresholds.bocpd_run_length_max:
            return None

        # 3. Price-stability: range over the last N bars is <= max %.
        recent = [
            b for b in window.bars
            if (window.as_of - b["ts"]) <= timedelta(minutes=self.thresholds.price_stability_window_min)
        ]
        if len(recent) < 5:
            return None
        highs = [float(b["high"]) for b in recent]
        lows = [float(b["low"]) for b in recent]
        rng_pct = (max(highs) - min(lows)) / min(lows) * 100.0
        if rng_pct > self.thresholds.price_range_pct_max:
            return None

        # 4. No new low in the last `no_new_low_window_min` minutes.
        if self._cascade_low_ts is not None:
            elapsed = (window.as_of - self._cascade_low_ts).total_seconds() / 60.0
            if elapsed < self.thresholds.no_new_low_window_min:
                return None

        # 5. OFI reversion (UPGRADES §1.2): cumulative imbalance has lifted off bottom.
        ofi = rf.order_flow_imbalance(window)
        if ofi < self.thresholds.ofi_reversion_threshold:
            return None

        # All checks passed — exhaustion confirmed.
        return Signal(
            name="refractory.cascade_exhausted",
            confidence=min(1.0, 1.0 - rl / max(self.thresholds.bocpd_run_length_max, 1)),
            features={
                "velocity_pct_of_peak": velocity_ratio_pct,
                "bocpd_run_length": float(rl),
                "bocpd_cp_prob": self.bocpd.changepoint_probability,
                "range_pct": rng_pct,
                "ofi": ofi,
            },
            note=f"exhaustion @{window.as_of.isoformat()} ({self.symbol})",
        )


# ─────────────────────────── multi-asset contagion (UPGRADES §1.3) ───────────────────────────

def contagion_multiplier(symbol_drops: dict[str, float], *, threshold_pct: float = 2.0) -> float:
    """Boost cascade confidence when multiple correlated symbols drop together.

    Returns a multiplier in [1.0, 2.0]: 1.0 if only one symbol crashes,
    up to 2.0 when 4+ correlated symbols crash by `threshold_pct` or more.
    """
    coincident = sum(1 for d in symbol_drops.values() if d >= threshold_pct)
    return min(2.0, 1.0 + 0.25 * coincident)
