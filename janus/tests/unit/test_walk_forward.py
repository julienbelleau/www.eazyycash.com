"""Walk-forward harness tests.

We don't run real Optuna here (slow) — we test the fold generator and the
report aggregation. A separate integration test exercises Optuna on a toy
problem.
"""

from __future__ import annotations

from datetime import datetime, timezone

from janus.backtest.metrics import BacktestSummary
from janus.backtest.walk_forward import (
    Fold,
    FoldResult,
    WalkForwardReport,
    make_anchored_folds,
)


def _summary(sharpe: float, n_trades: int = 100) -> BacktestSummary:
    return BacktestSummary(
        n_trades=n_trades, sharpe=sharpe, sortino=sharpe * 1.2, calmar=sharpe * 1.5,
        max_dd=0.10, dd_duration_bars=100, total_return=0.5, annualised_return=0.4,
        annualised_vol=0.20, win_rate=0.6, profit_factor=1.8, expectancy=10.0,
        tail_ratio=2.0, var_95=0.02, cvar_95=0.03,
    )


def test_make_anchored_folds_step_3m() -> None:
    start = datetime(2022, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, tzinfo=timezone.utc)
    folds = make_anchored_folds(start=start, end=end, train_months=18, test_months=6, step_months=3)
    assert len(folds) > 0
    # Anchored: train_start == start for every fold.
    assert all(f.train_start == start for f in folds)
    # Test windows progress by 3 months.
    diffs = [(folds[i + 1].test_start - folds[i].test_start).days for i in range(len(folds) - 1)]
    assert all(80 <= d <= 100 for d in diffs)  # ~90 days


def test_walk_forward_report_aggregates() -> None:
    folds = [
        Fold(
            train_start=datetime(2022, 1, 1, tzinfo=timezone.utc),
            train_end=datetime(2023, 7, 1, tzinfo=timezone.utc),
            test_start=datetime(2023, 7, 1, tzinfo=timezone.utc),
            test_end=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
    ]
    results = [
        FoldResult(
            fold=folds[0],
            best_params={"x": 0.5, "y": 100.0},
            train_summary=_summary(2.0),
            test_summary=_summary(s),
        )
        for s in (1.5, 1.2, 1.8)
    ]
    report = WalkForwardReport(folds=results)
    assert report.median_test_sharpe() == 1.5
    assert report.worst_test_sharpe() == 1.2


def test_parameter_stability_zero_when_constant() -> None:
    f = Fold(
        train_start=datetime(2022, 1, 1, tzinfo=timezone.utc),
        train_end=datetime(2023, 7, 1, tzinfo=timezone.utc),
        test_start=datetime(2023, 7, 1, tzinfo=timezone.utc),
        test_end=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    results = [
        FoldResult(fold=f, best_params={"x": 0.5},
                   train_summary=_summary(2.0), test_summary=_summary(1.5))
        for _ in range(5)
    ]
    report = WalkForwardReport(folds=results)
    stab = report.parameter_stability()
    assert stab["x"] == 0.0  # zero std = zero CV
