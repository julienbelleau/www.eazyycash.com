"""Stress tests required by the plan §10.

Every strategy must pass these before paper trading begins.

1. Bootstrap on trade order (1000 iterations) → distribution of Sharpe
2. Sensitivity analysis: ±20% on each numeric parameter → graceful degradation
3. Removed top/bottom 5% of trades — strategy must remain profitable
4. Stress historical events — performance during LUNA, FTX, COVID, etc.
5. Synthetic data via geometric Brownian motion paths

The output of each function is a numpy array of Sharpe values (or other
metric). Callers decide on pass/fail thresholds.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import numpy as np

from janus.backtest.metrics import TradeRecord, sharpe


def _equity_from_trades(trades: Sequence[TradeRecord], starting: float = 100_000.0) -> np.ndarray:
    eq = [starting]
    for t in trades:
        eq.append(eq[-1] + t.pnl_quote)
    return np.array(eq, dtype=float)


# ─────────────────────────── 1. bootstrap ───────────────────────────

def bootstrap_sharpe(trades: Sequence[TradeRecord], *, n_iter: int = 1000,
                     ann_factor: float = 252.0, seed: int = 42) -> np.ndarray:
    """Resample the trade order N times; return the Sharpe distribution.

    Trades are sampled WITH replacement — this answers "how Sharpe-like would
    the strategy have looked if luck had reordered or omitted some trades?"
    `ann_factor` should be set to the *number of trades per year*, not the
    bar cadence.
    """
    if not trades:
        return np.array([])
    rng = np.random.default_rng(seed)
    pnls = np.array([t.pnl_quote for t in trades])
    n = len(pnls)
    out = np.empty(n_iter, dtype=float)
    for i in range(n_iter):
        sample = rng.choice(pnls, size=n, replace=True)
        eq = np.concatenate(([100_000.0], 100_000.0 + np.cumsum(sample)))
        out[i] = sharpe(eq, ann_factor=ann_factor)
    return out


# ─────────────────────────── 2. sensitivity ───────────────────────────

@dataclass(frozen=True, slots=True)
class SensitivityRow:
    param: str
    multiplier: float       # 0.8 / 1.2 etc.
    sharpe: float


def sensitivity_sweep(
    base_params: Mapping[str, Any],
    *,
    runner: Callable[[Mapping[str, Any]], float],
    deltas: Sequence[float] = (0.8, 0.9, 1.1, 1.2),
) -> list[SensitivityRow]:
    """Vary each *numeric* base param by `deltas` and record the Sharpe."""
    rows: list[SensitivityRow] = []
    for key, val in base_params.items():
        if not isinstance(val, (int, float)):
            continue
        for d in deltas:
            cfg = dict(base_params)
            cfg[key] = type(val)(val * d)
            try:
                s = runner(cfg)
            except Exception:  # noqa: BLE001
                s = float("nan")
            rows.append(SensitivityRow(param=key, multiplier=d, sharpe=s))
    return rows


def graceful_degradation(rows: Sequence[SensitivityRow], *, base_sharpe: float,
                          drop_max_frac: float = 0.5) -> bool:
    """Pass iff no perturbed Sharpe drops more than `drop_max_frac` from base."""
    if base_sharpe <= 0:
        return False
    floor = base_sharpe * (1.0 - drop_max_frac)
    return all((not np.isnan(r.sharpe)) and r.sharpe >= floor for r in rows)


# ─────────────────────────── 3. removed trades ───────────────────────────

@dataclass(frozen=True, slots=True)
class RemovedTradesResult:
    full_sharpe: float
    removed_top_sharpe: float
    removed_bottom_sharpe: float


def removed_extreme_trades_test(
    trades: Sequence[TradeRecord], *, frac: float = 0.05,
    ann_factor: float = 252.0,
) -> RemovedTradesResult:
    if len(trades) < 20:
        return RemovedTradesResult(0.0, 0.0, 0.0)
    sorted_trades = sorted(trades, key=lambda t: t.pnl_quote)
    n_remove = max(1, int(len(trades) * frac))
    minus_top = sorted_trades[:-n_remove]
    minus_bottom = sorted_trades[n_remove:]
    return RemovedTradesResult(
        full_sharpe=sharpe(_equity_from_trades(trades), ann_factor=ann_factor),
        removed_top_sharpe=sharpe(_equity_from_trades(minus_top), ann_factor=ann_factor),
        removed_bottom_sharpe=sharpe(_equity_from_trades(minus_bottom), ann_factor=ann_factor),
    )


# ─────────────────────────── 4. historical stress events ───────────────────────────

# Dates expressed as (start, end) in YYYY-MM-DD; the engine slices the backtest
# to these and reports the per-event metrics.
HISTORICAL_STRESS_EVENTS: list[tuple[str, str, str]] = [
    ("LUNA collapse",     "2022-05-08", "2022-05-15"),
    ("3AC unwind",        "2022-06-13", "2022-06-20"),
    ("FTX collapse",      "2022-11-06", "2022-11-15"),
    ("USDC depeg / SVB",  "2023-03-10", "2023-03-13"),
    ("Yen carry unwind",  "2024-08-04", "2024-08-08"),
    ("COVID Mar 2020",    "2020-03-09", "2020-03-15"),
    ("China ban May 2021","2021-05-19", "2021-05-23"),
]


# ─────────────────────────── 5. synthetic Monte Carlo paths ───────────────────────────

def gbm_paths(*, mu: float = 0.0, sigma: float = 0.02, n_paths: int = 100,
              n_steps: int = 525_600, s0: float = 40_000.0, seed: int = 42) -> np.ndarray:
    """Generate `n_paths` of GBM with daily-equivalent drift and per-step vol.

    Returns shape (n_paths, n_steps + 1). Useful for "would the strategy
    profit on data that has no edge?" — strategies that are profitable on
    pure-noise GBM are overfit.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0
    eps = rng.standard_normal((n_paths, n_steps))
    log_steps = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * eps
    log_paths = np.concatenate(
        [np.zeros((n_paths, 1)), np.cumsum(log_steps, axis=1)], axis=1
    )
    return s0 * np.exp(log_paths)
