"""Backtest performance metrics.

All metrics are computed from a series of `(timestamp, equity)` points and a
list of closed trades. The functions are pure (no I/O) and operate on
plain numpy arrays — easily unit-testable.

Conventions:
- Returns are *log returns* unless the metric explicitly requires simple.
- Annualisation factor `ann_factor` defaults to 525_600 (minutes in a year)
  because Janus runs at 1m granularity. Override for daily series.
- Ratios are computed assuming risk-free rate ~ 0. Crypto traders typically
  benchmark against a 0% rf since BTC HODL is the natural alternative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

import numpy as np


_MINUTES_PER_YEAR = 365.25 * 24 * 60


@dataclass(frozen=True, slots=True)
class TradeRecord:
    pnl_quote: float          # realised P&L in quote currency (USD)
    return_pct: float         # P&L as fraction of capital deployed (signed)
    entry_ts_utc_minute: int  # unix minute (for ordering / windowing)
    exit_ts_utc_minute: int


def _log_returns(equity: np.ndarray) -> np.ndarray:
    if len(equity) < 2:
        return np.array([])
    ratios = equity[1:] / equity[:-1]
    # Guard against division producing 0 (full liquidation): replace with -inf-bounded value.
    ratios = np.clip(ratios, 1e-9, None)
    return np.log(ratios)


def total_return(equity: np.ndarray) -> float:
    if len(equity) < 2:
        return 0.0
    return float(equity[-1] / equity[0] - 1.0)


def annualised_return(equity: np.ndarray, *, ann_factor: float = _MINUTES_PER_YEAR) -> float:
    n = len(equity)
    if n < 2:
        return 0.0
    periods = n - 1
    return float((equity[-1] / equity[0]) ** (ann_factor / periods) - 1.0)


def annualised_vol(equity: np.ndarray, *, ann_factor: float = _MINUTES_PER_YEAR) -> float:
    r = _log_returns(equity)
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=1) * np.sqrt(ann_factor))


def sharpe(equity: np.ndarray, *, ann_factor: float = _MINUTES_PER_YEAR) -> float:
    r = _log_returns(equity)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(ann_factor))


def sortino(equity: np.ndarray, *, ann_factor: float = _MINUTES_PER_YEAR) -> float:
    r = _log_returns(equity)
    if len(r) < 2:
        return 0.0
    downside = r[r < 0]
    if len(downside) == 0 or downside.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / downside.std(ddof=1) * np.sqrt(ann_factor))


def max_drawdown(equity: np.ndarray) -> float:
    """Returns the worst peak-to-trough drawdown as a positive fraction in [0, 1]."""
    if len(equity) < 2:
        return 0.0
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / running_max
    return float(-dd.min())


def drawdown_duration(equity: np.ndarray) -> int:
    """Worst-case drawdown duration in periods (bars)."""
    if len(equity) < 2:
        return 0
    running_max = np.maximum.accumulate(equity)
    in_dd = equity < running_max
    longest = current = 0
    for x in in_dd:
        current = current + 1 if x else 0
        longest = max(longest, current)
    return longest


def calmar(equity: np.ndarray, *, ann_factor: float = _MINUTES_PER_YEAR) -> float:
    dd = max_drawdown(equity)
    if dd == 0:
        return 0.0
    return annualised_return(equity, ann_factor=ann_factor) / dd


def win_rate(trades: Iterable[TradeRecord]) -> float:
    trades = list(trades)
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl_quote > 0)
    return wins / len(trades)


def profit_factor(trades: Iterable[TradeRecord]) -> float:
    gross_win = sum(t.pnl_quote for t in trades if t.pnl_quote > 0)
    gross_loss = -sum(t.pnl_quote for t in trades if t.pnl_quote < 0)
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return gross_win / gross_loss


def expectancy(trades: Iterable[TradeRecord]) -> float:
    trades = list(trades)
    if not trades:
        return 0.0
    return float(np.mean([t.pnl_quote for t in trades]))


def tail_ratio(equity: np.ndarray, *, q_lo: float = 0.05, q_hi: float = 0.95) -> float:
    r = _log_returns(equity)
    if len(r) < 20:
        return 0.0
    p_hi = np.quantile(r, q_hi)
    p_lo = np.quantile(r, q_lo)
    if p_lo == 0:
        return 0.0
    return float(p_hi / abs(p_lo))


def value_at_risk(equity: np.ndarray, *, alpha: float = 0.95) -> float:
    """Historical 1-period VaR at confidence `alpha` (returned as positive fraction)."""
    r = _log_returns(equity)
    if len(r) < 20:
        return 0.0
    return float(-np.quantile(r, 1.0 - alpha))


def conditional_var(equity: np.ndarray, *, alpha: float = 0.95) -> float:
    """CVaR / Expected Shortfall — the average loss in the alpha-tail."""
    r = _log_returns(equity)
    if len(r) < 20:
        return 0.0
    threshold = np.quantile(r, 1.0 - alpha)
    tail = r[r <= threshold]
    if len(tail) == 0:
        return 0.0
    return float(-tail.mean())


def beta_to_benchmark(strat_equity: np.ndarray, bench_equity: np.ndarray) -> float:
    """OLS beta of strategy returns against benchmark returns (e.g. BTC HODL)."""
    rs = _log_returns(strat_equity)
    rb = _log_returns(bench_equity)
    n = min(len(rs), len(rb))
    if n < 2:
        return 0.0
    rs = rs[-n:]
    rb = rb[-n:]
    cov = float(np.cov(rs, rb, ddof=1)[0, 1])
    var_b = float(rb.var(ddof=1))
    return cov / var_b if var_b > 0 else 0.0


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    n_trades: int
    sharpe: float
    sortino: float
    calmar: float
    max_dd: float
    dd_duration_bars: int
    total_return: float
    annualised_return: float
    annualised_vol: float
    win_rate: float
    profit_factor: float
    expectancy: float
    tail_ratio: float
    var_95: float
    cvar_95: float

    def passes_phase1_gate(self, min_sharpe: float = 1.5, min_calmar: float = 2.0,
                           max_dd: float = 0.15, min_win_rate: float = 0.55,
                           min_profit_factor: float = 1.6, min_trades: int = 50) -> bool:
        return (
            self.sharpe >= min_sharpe
            and self.calmar >= min_calmar
            and self.max_dd <= max_dd
            and self.win_rate >= min_win_rate
            and self.profit_factor >= min_profit_factor
            and self.n_trades >= min_trades
        )


def summarise(equity: np.ndarray, trades: Iterable[TradeRecord],
              *, ann_factor: float = _MINUTES_PER_YEAR) -> BacktestSummary:
    trades_list = list(trades)
    return BacktestSummary(
        n_trades=len(trades_list),
        sharpe=sharpe(equity, ann_factor=ann_factor),
        sortino=sortino(equity, ann_factor=ann_factor),
        calmar=calmar(equity, ann_factor=ann_factor),
        max_dd=max_drawdown(equity),
        dd_duration_bars=drawdown_duration(equity),
        total_return=total_return(equity),
        annualised_return=annualised_return(equity, ann_factor=ann_factor),
        annualised_vol=annualised_vol(equity, ann_factor=ann_factor),
        win_rate=win_rate(trades_list),
        profit_factor=profit_factor(trades_list),
        expectancy=expectancy(trades_list),
        tail_ratio=tail_ratio(equity),
        var_95=value_at_risk(equity, alpha=0.95),
        cvar_95=conditional_var(equity, alpha=0.95),
    )
