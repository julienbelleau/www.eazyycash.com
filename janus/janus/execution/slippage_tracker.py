"""Live slippage tracker.

Continuously compares realised vs expected slippage. If the rolling delta
exceeds a threshold over a window, raises an alert (and optionally trips a
kill switch). Plan §9 + §8.4.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class SlippageTracker:
    window: int = 20
    drift_factor_alert: float = 1.5      # 50% over expectation across the window
    drift_factor_kill: float = 3.0       # 3× over expectation triggers kill switch

    expected: deque[float] = field(default_factory=lambda: deque(maxlen=20))
    realised: deque[float] = field(default_factory=lambda: deque(maxlen=20))

    def __post_init__(self) -> None:
        self.expected = deque(maxlen=self.window)
        self.realised = deque(maxlen=self.window)

    def record(self, expected_bps: float, realised_bps: float) -> None:
        self.expected.append(expected_bps)
        self.realised.append(realised_bps)

    @property
    def n_observed(self) -> int:
        return len(self.realised)

    def drift_ratio(self) -> float:
        if not self.expected or not self.realised:
            return 0.0
        e = sum(self.expected) / len(self.expected)
        r = sum(self.realised) / len(self.realised)
        if e <= 0:
            return float("inf") if r > 0 else 0.0
        return r / e

    def should_alert(self) -> bool:
        return self.n_observed >= self.window and self.drift_ratio() >= self.drift_factor_alert

    def should_kill(self) -> bool:
        return self.n_observed >= self.window and self.drift_ratio() >= self.drift_factor_kill
