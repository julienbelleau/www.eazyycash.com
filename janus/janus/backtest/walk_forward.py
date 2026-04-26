"""Walk-forward harness with Optuna multivariate TPE.

Per the plan §10:
  Train window: 18 months
  Test window:  6 months (out-of-sample)
  Step:         3 months

For each fold, Optuna searches the strategy's parameter space on the train
window, then we evaluate the best params on the test window. The aggregator
emits the *median* OOS Sharpe (more robust than mean) and the *worst-fold*
Sharpe — the latter is the gate against fold-cherry-picking.

Optuna's `sampler="tpe"` with `multivariate=True` is the right choice for
correlated knobs (e.g. cascade thresholds + exit thresholds). `n_startup_trials`
is sized so TPE has decent prior coverage before it starts to exploit.

This module is intentionally engine-agnostic — it expects a `runner`
callable `(params, train, test) -> BacktestSummary`. The runner builds the
strategy and engine; this module owns the *search* and *aggregation*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import optuna
from loguru import logger

from janus.backtest.metrics import BacktestSummary


@dataclass(frozen=True, slots=True)
class Fold:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


@dataclass(frozen=True, slots=True)
class FoldResult:
    fold: Fold
    best_params: dict[str, Any]
    train_summary: BacktestSummary
    test_summary: BacktestSummary


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    folds: list[FoldResult]

    def median_test_sharpe(self) -> float:
        if not self.folds:
            return 0.0
        return float(np.median([f.test_summary.sharpe for f in self.folds]))

    def worst_test_sharpe(self) -> float:
        if not self.folds:
            return 0.0
        return float(min(f.test_summary.sharpe for f in self.folds))

    def parameter_stability(self) -> dict[str, float]:
        """For each param key, return std/|mean|. Lower = more stable."""
        if not self.folds:
            return {}
        keys = set().union(*(f.best_params.keys() for f in self.folds))
        out: dict[str, float] = {}
        for k in keys:
            vals = [float(f.best_params.get(k, np.nan)) for f in self.folds]
            arr = np.array([v for v in vals if not np.isnan(v)])
            if len(arr) < 2:
                out[k] = 0.0
                continue
            mean = abs(arr.mean())
            out[k] = float(arr.std(ddof=1) / mean) if mean > 0 else float("inf")
        return out


def make_anchored_folds(
    *, start: datetime, end: datetime,
    train_months: int = 18, test_months: int = 6, step_months: int = 3,
) -> list[Fold]:
    """Anchored walk-forward folds: train always starts at `start`.

    We use 30-day months for arithmetic — the small jitter is acceptable for
    fold boundaries.
    """
    folds: list[Fold] = []
    train_start = start
    cursor = train_start + timedelta(days=30 * train_months)
    while cursor + timedelta(days=30 * test_months) <= end:
        folds.append(Fold(
            train_start=train_start,
            train_end=cursor,
            test_start=cursor,
            test_end=cursor + timedelta(days=30 * test_months),
        ))
        cursor += timedelta(days=30 * step_months)
    return folds


# ─────────────────────────── Optuna search ───────────────────────────

ParamSpace = Mapping[str, Callable[[optuna.Trial], Any]]
"""Maps a param name to a function that draws from its distribution.

Example::
    {
        "cascade.price_drop_pct_min": lambda trial: trial.suggest_float("price_drop_pct_min", 2.0, 8.0),
        "cascade.liq_usd_min": lambda trial: trial.suggest_float("liq_usd_min", 100e6, 500e6, log=True),
    }
"""


Runner = Callable[[Mapping[str, Any], datetime, datetime], BacktestSummary]


def _objective_factory(
    space: ParamSpace, runner: Runner,
    train_start: datetime, train_end: datetime,
) -> Callable[[optuna.Trial], float]:
    def objective(trial: optuna.Trial) -> float:
        params = {k: f(trial) for k, f in space.items()}
        try:
            summary = runner(params, train_start, train_end)
        except Exception as exc:  # noqa: BLE001
            logger.warning("optuna trial errored: {}", exc)
            return -10.0
        # We optimise Sharpe with a min-trades guard.
        if summary.n_trades < 20:
            return -5.0
        return summary.sharpe

    return objective


def run_fold(
    fold: Fold, *, space: ParamSpace, runner: Runner,
    n_trials: int = 50, n_startup_trials: int = 10, seed: int = 42,
) -> FoldResult:
    sampler = optuna.samplers.TPESampler(
        multivariate=True, seed=seed, n_startup_trials=n_startup_trials,
    )
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(
        _objective_factory(space, runner, fold.train_start, fold.train_end),
        n_trials=n_trials,
        show_progress_bar=False,
    )
    best_params = study.best_params
    train_summary = runner(best_params, fold.train_start, fold.train_end)
    test_summary = runner(best_params, fold.test_start, fold.test_end)
    logger.bind(
        fold_train=f"{fold.train_start:%Y-%m-%d}__{fold.train_end:%Y-%m-%d}",
        sharpe_train=round(train_summary.sharpe, 3),
        sharpe_test=round(test_summary.sharpe, 3),
    ).info("fold complete")
    return FoldResult(fold=fold, best_params=best_params,
                      train_summary=train_summary, test_summary=test_summary)


def walk_forward(
    folds: Iterable[Fold], *, space: ParamSpace, runner: Runner,
    n_trials: int = 50, n_startup_trials: int = 10, seed: int = 42,
) -> WalkForwardReport:
    results = [
        run_fold(f, space=space, runner=runner,
                 n_trials=n_trials, n_startup_trials=n_startup_trials, seed=seed)
        for f in folds
    ]
    return WalkForwardReport(folds=results)
