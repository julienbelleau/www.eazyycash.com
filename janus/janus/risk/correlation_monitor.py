"""Inter-strategy correlation monitor (plan §8).

The strategies are designed to be decorrelated. If realised P&L correlation
between two strategies exceeds 0.6, it's a sign that either:
  (a) the regime is one where their signals overlap (e.g. crisis triggers
      both refractory and stablecoin), or
  (b) there's a bug — they're trading the same thing.

The monitor maintains rolling 30-day correlation matrices over per-strategy
daily P&L and exposes a `get_correlation()` and `should_dampen()` API.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date

import numpy as np


@dataclass
class CorrelationMonitor:
    window_days: int = 30
    pnl_history: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=30)))
    dampen_threshold: float = 0.6
    disarm_threshold: float = 0.8

    def __post_init__(self) -> None:
        self.pnl_history = defaultdict(lambda: deque(maxlen=self.window_days))

    def record_daily(self, pnl_by_strategy: dict[str, float]) -> None:
        for sid, pnl in pnl_by_strategy.items():
            self.pnl_history[sid].append(pnl)

    def correlation(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        sa, sb = self.pnl_history.get(a), self.pnl_history.get(b)
        if not sa or not sb:
            return 0.0
        n = min(len(sa), len(sb))
        if n < 5:
            return 0.0
        x = np.array(list(sa)[-n:])
        y = np.array(list(sb)[-n:])
        if x.std(ddof=1) == 0 or y.std(ddof=1) == 0:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    def adjustment_for(self, strategy: str, peers: list[str]) -> float:
        """Return a multiplier in {1.0, 0.5, 0.0} based on max correlation with peers."""
        if not peers:
            return 1.0
        max_corr = max(abs(self.correlation(strategy, p)) for p in peers if p != strategy)
        if max_corr >= self.disarm_threshold:
            return 0.0
        if max_corr >= self.dampen_threshold:
            return 0.5
        return 1.0
