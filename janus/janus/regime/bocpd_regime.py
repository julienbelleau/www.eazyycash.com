"""BOCPD-based regime *transition* detector.

The HMM gives a smooth, slow-moving classification. BOCPD on BTC returns
gives a *fast* signal of regime *transition* — useful for catching pivots
the HMM hasn't caught up to yet (UPGRADES §4.1).

We run BOCPD on the *vol-of-vol* series (rolling-window std of |returns|)
because that's where regime transitions show up most cleanly: a calm
trending market has low vol-of-vol; transitions to crisis or recovery
spike it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from janus.features.bocpd import Bocpd


@dataclass
class BocpdRegimeTransitionDetector:
    bocpd: Bocpd
    transition_threshold_run_length: int = 10

    @classmethod
    def make(cls, hazard_lambda: float = 200.0) -> "BocpdRegimeTransitionDetector":
        return cls(bocpd=Bocpd.make(hazard_lambda=hazard_lambda))

    def update(self, vol_of_vol: float) -> None:
        self.bocpd.update(vol_of_vol)

    @property
    def is_transitioning(self) -> bool:
        """True iff the MAP run length is below the threshold (recent CP)."""
        return self.bocpd.run_length_map < self.transition_threshold_run_length

    @property
    def transition_probability(self) -> float:
        return float(self.bocpd.changepoint_probability)


def vol_of_vol(returns: np.ndarray, *, vol_window: int = 14, vov_window: int = 14) -> float:
    """Compute vol-of-vol on a series of log returns (most recent observation)."""
    if len(returns) < vol_window + vov_window:
        return 0.0
    # Rolling vol window, then std of those vols over vov_window periods.
    vols: list[float] = []
    for i in range(len(returns) - vol_window + 1):
        window = returns[i:i + vol_window]
        vols.append(float(window.std(ddof=1)))
    if len(vols) < vov_window:
        return 0.0
    return float(np.std(vols[-vov_window:], ddof=1))
