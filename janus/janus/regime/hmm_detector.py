"""Hidden Markov Model regime detector.

Wraps `hmmlearn.GaussianHMM` for the 5-regime classification specified in
plan §7: trending bull, trending bear, range, crisis/cascade, recovery.

Inputs (computed elsewhere):
  - 7-day BTC log return
  - 14-day realised vol
  - BTC dominance change
  - latest funding rate
  - 14-day OI change

Training:
  - 2 years of daily features as the rolling window
  - re-trained monthly (caller's responsibility — this module just exposes
    `fit()` and `predict_proba()`)

Output:
  - posterior probability of each state at each time t
  - hard-classification = argmax with temporal smoothing (3-5 day kernel)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

try:
    from hmmlearn.hmm import GaussianHMM
except ImportError:  # pragma: no cover
    GaussianHMM = None  # type: ignore[assignment]


class Regime(StrEnum):
    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    RANGE = "range"
    CRISIS = "crisis"
    RECOVERY = "recovery"


REGIMES_ORDERED: tuple[Regime, ...] = (
    Regime.TRENDING_BULL, Regime.TRENDING_BEAR, Regime.RANGE,
    Regime.CRISIS, Regime.RECOVERY,
)


@dataclass
class HmmRegimeDetector:
    n_states: int = 5
    seed: int = 42
    smoothing_window: int = 5
    model: object = None  # GaussianHMM after fit()
    state_to_regime: dict[int, Regime] = field(default_factory=dict)

    def fit(self, X: np.ndarray) -> None:
        """Fit the HMM. `X` shape: (n_samples, n_features). Features must be
        normalised by the caller (z-scored, etc.)."""
        if GaussianHMM is None:
            raise ImportError("hmmlearn is not installed")
        if X.shape[0] < self.n_states * 30:
            raise ValueError(
                f"need at least {self.n_states * 30} samples, got {X.shape[0]}"
            )
        model = GaussianHMM(
            n_components=self.n_states, covariance_type="diag",
            n_iter=200, random_state=self.seed, tol=1e-4,
        )
        model.fit(X)
        self.model = model
        self.state_to_regime = self._label_states(X)

    def _label_states(self, X: np.ndarray) -> dict[int, Regime]:
        """Heuristically map HMM state ids → human regimes by their cluster means.

        We assume column 0 is BTC return, column 1 is volatility. The mapping
        rules (in priority order):
          - state with the highest vol AND lowest return → CRISIS
          - state with high return AND low vol → TRENDING_BULL
          - state with low return AND moderate-high vol → TRENDING_BEAR
          - state with mid return AND declining-vol vs CRISIS → RECOVERY
          - remaining → RANGE
        """
        if self.model is None:
            return {}
        means = self.model.means_   # type: ignore[attr-defined]
        # Score each state on (return_z, vol_z).
        ret = means[:, 0]
        vol = means[:, 1] if means.shape[1] > 1 else np.zeros(self.n_states)

        out: dict[int, Regime] = {}
        order_by_ret = np.argsort(ret)
        order_by_vol = np.argsort(vol)
        crisis_state = int(order_by_vol[-1])
        out[crisis_state] = Regime.CRISIS
        bull_state = int(order_by_ret[-1])
        if bull_state != crisis_state:
            out[bull_state] = Regime.TRENDING_BULL
        bear_state = int(order_by_ret[0])
        if bear_state not in out:
            out[bear_state] = Regime.TRENDING_BEAR

        remaining = [i for i in range(self.n_states) if i not in out]
        # Recovery = state with vol below crisis but return positive.
        recovery_candidates = [i for i in remaining if ret[i] > 0]
        if recovery_candidates:
            recovery = int(min(recovery_candidates, key=lambda i: vol[i]))
            out[recovery] = Regime.RECOVERY
        # Anything still unassigned → RANGE.
        for i in range(self.n_states):
            if i not in out:
                out[i] = Regime.RANGE
        return out

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("fit() must be called first")
        return self.model.predict_proba(X)  # type: ignore[attr-defined,no-any-return]

    def classify(self, X: np.ndarray) -> list[Regime]:
        """Hard classification with temporal smoothing.

        For each row of X, returns the regime with highest smoothed-probability.
        Smoothing = simple moving average over `smoothing_window` periods
        (suppresses single-day flip-flops mentioned in plan §7).
        """
        proba = self.predict_proba(X)
        if self.smoothing_window > 1:
            kernel = np.ones(self.smoothing_window) / self.smoothing_window
            proba = np.apply_along_axis(
                lambda col: np.convolve(col, kernel, mode="same"), axis=0, arr=proba
            )
        argmax = proba.argmax(axis=1)
        return [self.state_to_regime[int(s)] for s in argmax]
