"""Backtest metrics — math correctness + edge cases."""

from __future__ import annotations

import numpy as np
import pytest

from janus.backtest.metrics import (
    BacktestSummary,
    TradeRecord,
    annualised_return,
    annualised_vol,
    beta_to_benchmark,
    calmar,
    conditional_var,
    drawdown_duration,
    expectancy,
    max_drawdown,
    profit_factor,
    sharpe,
    sortino,
    summarise,
    tail_ratio,
    total_return,
    value_at_risk,
    win_rate,
)


def test_total_return_zero_on_empty() -> None:
    assert total_return(np.array([])) == 0.0
    assert total_return(np.array([100.0])) == 0.0


def test_total_return_simple() -> None:
    assert total_return(np.array([100.0, 110.0])) == 0.10


def test_sharpe_zero_when_no_variance() -> None:
    flat = np.array([100.0] * 10)
    assert sharpe(flat) == 0.0


def test_sharpe_positive_for_uptrending_series() -> None:
    rng = np.random.default_rng(42)
    log_returns = 0.001 + 0.01 * rng.standard_normal(1000)
    eq = 100.0 * np.exp(np.cumsum(log_returns))
    assert sharpe(eq, ann_factor=252.0) > 0


def test_max_drawdown_basic() -> None:
    eq = np.array([100.0, 120.0, 110.0, 130.0, 90.0, 110.0])
    # peak 130 -> trough 90 = -40 / 130 ≈ 0.3077
    assert abs(max_drawdown(eq) - 40.0 / 130.0) < 1e-9


def test_drawdown_duration() -> None:
    eq = np.array([100.0, 110.0, 105.0, 108.0, 112.0, 100.0])
    # Below peak (110) for indices 2, 3, then 5 → longest run = 2.
    assert drawdown_duration(eq) == 2


def test_calmar_handles_zero_dd() -> None:
    eq = np.array([100.0] * 10)
    assert calmar(eq) == 0.0


def test_win_rate_and_profit_factor() -> None:
    trades = [
        TradeRecord(pnl_quote=100.0, return_pct=0.01, entry_ts_utc_minute=0, exit_ts_utc_minute=1),
        TradeRecord(pnl_quote=-50.0, return_pct=-0.005, entry_ts_utc_minute=2, exit_ts_utc_minute=3),
        TradeRecord(pnl_quote=200.0, return_pct=0.02, entry_ts_utc_minute=4, exit_ts_utc_minute=5),
    ]
    assert win_rate(trades) == pytest.approx(2 / 3)
    assert profit_factor(trades) == pytest.approx(300.0 / 50.0)
    assert expectancy(trades) == pytest.approx(250.0 / 3)


def test_profit_factor_handles_no_losses() -> None:
    trades = [
        TradeRecord(pnl_quote=100.0, return_pct=0.01, entry_ts_utc_minute=0, exit_ts_utc_minute=1),
    ]
    assert profit_factor(trades) == float("inf")
    # No trades at all: 0
    assert profit_factor([]) == 0.0


def test_value_at_risk_and_cvar_bounds() -> None:
    rng = np.random.default_rng(7)
    eq = 100.0 * np.exp(np.cumsum(0.005 * rng.standard_normal(1000)))
    var = value_at_risk(eq, alpha=0.95)
    cvar = conditional_var(eq, alpha=0.95)
    assert var >= 0.0
    assert cvar >= var  # ES is always >= VaR


def test_tail_ratio_zero_on_short_series() -> None:
    assert tail_ratio(np.array([100.0, 101.0, 102.0])) == 0.0


def test_beta_one_to_self() -> None:
    rng = np.random.default_rng(1)
    eq = 100.0 * np.exp(np.cumsum(0.01 * rng.standard_normal(500)))
    b = beta_to_benchmark(eq, eq)
    assert abs(b - 1.0) < 1e-9


def test_summarise_returns_a_summary() -> None:
    eq = 100.0 + np.cumsum(np.random.default_rng(0).normal(0.05, 1.0, size=300))
    trades = [
        TradeRecord(pnl_quote=10.0, return_pct=0.001, entry_ts_utc_minute=i*10, exit_ts_utc_minute=i*10+5)
        for i in range(50)
    ]
    s = summarise(eq, trades, ann_factor=252.0)
    assert isinstance(s, BacktestSummary)
    assert s.n_trades == 50


def test_phase1_gate_predicate() -> None:
    s = BacktestSummary(
        n_trades=60, sharpe=1.6, sortino=2.0, calmar=2.5, max_dd=0.10,
        dd_duration_bars=100, total_return=0.5, annualised_return=0.4,
        annualised_vol=0.20, win_rate=0.60, profit_factor=2.0,
        expectancy=100.0, tail_ratio=2.0, var_95=0.02, cvar_95=0.03,
    )
    assert s.passes_phase1_gate()
    s_low = BacktestSummary(**{**s.__dict__, "sharpe": 1.0})
    assert not s_low.passes_phase1_gate()


def test_annualised_return_compounding() -> None:
    # 1% growth per period for 252 periods → ~14× / year @ ann_factor 252
    eq = 100.0 * (1.01 ** np.arange(253))
    ar = annualised_return(eq, ann_factor=252.0)
    assert abs(ar - (1.01 ** 252 - 1.0)) < 1e-6


def test_sortino_uses_downside_only() -> None:
    eq = 100.0 + np.cumsum(np.array([1.0] * 100 + [-1.0] * 5))
    s_o = sortino(eq, ann_factor=252.0)
    s = sharpe(eq, ann_factor=252.0)
    # Sortino should be different from Sharpe when distribution is skewed.
    assert s_o != s


def test_annualised_vol_zero_on_flat() -> None:
    assert annualised_vol(np.array([100.0] * 10)) == 0.0
