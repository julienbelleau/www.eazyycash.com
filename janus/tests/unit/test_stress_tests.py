"""Stress test module — bootstrap, sensitivity, removed extremes, GBM paths."""

from __future__ import annotations

import numpy as np

from janus.backtest.metrics import TradeRecord
from janus.backtest.stress_tests import (
    bootstrap_sharpe,
    gbm_paths,
    graceful_degradation,
    removed_extreme_trades_test,
    sensitivity_sweep,
)


def _make_trades(n: int, mean_pnl: float = 50.0, sd: float = 100.0, seed: int = 0) -> list[TradeRecord]:
    rng = np.random.default_rng(seed)
    pnls = rng.normal(mean_pnl, sd, size=n)
    return [
        TradeRecord(pnl_quote=float(p), return_pct=float(p / 10_000),
                    entry_ts_utc_minute=i, exit_ts_utc_minute=i + 1)
        for i, p in enumerate(pnls)
    ]


def test_bootstrap_returns_distribution() -> None:
    trades = _make_trades(200, mean_pnl=80.0, sd=100.0, seed=1)
    dist = bootstrap_sharpe(trades, n_iter=300, ann_factor=252.0, seed=42)
    assert len(dist) == 300
    # Mean Sharpe of resampled iid trades should be positive (positive expectancy).
    assert dist.mean() > 0


def test_bootstrap_handles_empty() -> None:
    assert len(bootstrap_sharpe([])) == 0


def test_sensitivity_sweep_skips_non_numeric() -> None:
    base = {"x": 1.0, "y": 2.0, "name": "abc"}
    rows = sensitivity_sweep(base, runner=lambda p: p["x"] * p["y"], deltas=(0.8, 1.2))
    # 2 numeric params * 2 deltas = 4 rows; 'name' skipped.
    assert len(rows) == 4
    assert {r.param for r in rows} == {"x", "y"}


def test_graceful_degradation_pass_when_within_tolerance() -> None:
    from janus.backtest.stress_tests import SensitivityRow
    rows = [
        SensitivityRow("x", 0.8, 1.5),
        SensitivityRow("x", 1.2, 1.6),
        SensitivityRow("y", 0.8, 1.4),
    ]
    assert graceful_degradation(rows, base_sharpe=2.0, drop_max_frac=0.5)
    assert not graceful_degradation(rows, base_sharpe=2.0, drop_max_frac=0.20)


def test_removed_extreme_trades() -> None:
    trades = _make_trades(100, mean_pnl=50.0, sd=200.0, seed=2)
    res = removed_extreme_trades_test(trades, frac=0.05, ann_factor=252.0)
    # Removing best should hurt Sharpe; removing worst should help.
    assert res.removed_top_sharpe <= res.full_sharpe
    assert res.removed_bottom_sharpe >= res.full_sharpe


def test_gbm_paths_shape() -> None:
    paths = gbm_paths(n_paths=10, n_steps=100)
    assert paths.shape == (10, 101)
    # Initial value matches s0.
    assert all(paths[:, 0] == 40_000.0)


def test_gbm_paths_deterministic_with_seed() -> None:
    a = gbm_paths(n_paths=5, n_steps=50, seed=42)
    b = gbm_paths(n_paths=5, n_steps=50, seed=42)
    np.testing.assert_array_equal(a, b)
