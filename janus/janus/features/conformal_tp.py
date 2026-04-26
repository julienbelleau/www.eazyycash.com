"""Split-conformal prediction for take-profit calibration (UPGRADES §1.5).

Why this exists:
- The original plan exits at a fixed 50% retracement of the cascade drop.
  That number is arbitrary; some cascades retrace 80%, others stop at 30%.
- A *calibrated* TP is one such that "actual retracement >= TP" with a
  guaranteed coverage rate (e.g. 90%).
- Split-conformal prediction (Vovk, Shafer; Lei et al.) provides this with
  no distributional assumptions on the residuals — finite-sample valid.

Usage::
    cal = SplitConformal()
    cal.fit(predicted=preds, observed=obs)         # calibration set
    interval = cal.predict_interval(point=0.5, alpha=0.10)
    # interval is (lower, upper) covering observed retracement w.p. >= 90%.

The strategy reads `interval.lower` as the *conservative* TP — i.e. exit
when realised retracement reaches the lower bound; this gives the calibrated
coverage guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class ConformalInterval:
    point: float
    lower: float
    upper: float
    coverage_target: float


@dataclass
class SplitConformal:
    """Symmetric split-conformal regressor on residuals.

    Use case in Janus: model the *expected* retracement post-cascade based on
    cascade severity (the `point` argument), then widen by the alpha-quantile
    of |observed - predicted| from the calibration set.
    """

    residuals: np.ndarray = None  # type: ignore[assignment]

    def fit(self, predicted: Sequence[float], observed: Sequence[float]) -> None:
        if len(predicted) != len(observed):
            raise ValueError("predicted and observed must have equal length")
        if len(predicted) < 20:
            raise ValueError(f"need at least 20 calibration points, got {len(predicted)}")
        residuals = np.abs(np.asarray(observed) - np.asarray(predicted))
        self.residuals = np.sort(residuals)

    def predict_interval(self, point: float, alpha: float = 0.10) -> ConformalInterval:
        if self.residuals is None:
            raise ValueError("fit() must be called first")
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        # 1 - alpha quantile of residuals (right-handed; Lei et al. correction).
        n = len(self.residuals)
        q_idx = int(np.ceil((n + 1) * (1.0 - alpha)) - 1)
        q_idx = max(0, min(q_idx, n - 1))
        q = float(self.residuals[q_idx])
        return ConformalInterval(
            point=point, lower=point - q, upper=point + q, coverage_target=1.0 - alpha,
        )

    def empirical_coverage(self, point: float, alpha: float = 0.10,
                            new_observed: Sequence[float] | None = None) -> float:
        """Compute the empirical coverage on a held-out set (sanity check)."""
        if new_observed is None:
            return 0.0
        interval = self.predict_interval(point, alpha=alpha)
        obs = np.asarray(new_observed)
        return float(((obs >= interval.lower) & (obs <= interval.upper)).mean())
