"""Kill switches.

Per plan §8 + §9, several conditions force the system to pause or stop:

- Latency: >5s on 3 consecutive orders → 1h pause
- Slippage drift: realised slippage > 3× expected on 5 trades → strategy pause
- P&L drift: realised P&L diverges from expected by >30% over 7 days → alert + pause
- Drawdown: portfolio -20% → halt + manual intervention

The KillSwitchRegistry stores all switches; each switch is a callable that
returns (tripped, reason). The Engine polls them on every tick.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum


class KillScope(StrEnum):
    PORTFOLIO = "portfolio"     # halts everything
    STRATEGY = "strategy"       # halts a single strategy
    EXCHANGE = "exchange"       # halts trading on one exchange


@dataclass(frozen=True, slots=True)
class KillEvent:
    scope: KillScope
    target: str
    reason: str
    triggered_at: datetime
    auto_resume_after: timedelta | None = None


class KillSwitchRegistry:
    """Thread-safe registry of active kill events.

    Used by the engine: before submitting any order, the engine consults
    `is_tripped(scope, target)` and refuses if True.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: list[KillEvent] = []

    def trip(self, scope: KillScope, target: str, reason: str,
             auto_resume_after: timedelta | None = None) -> KillEvent:
        with self._lock:
            event = KillEvent(scope=scope, target=target, reason=reason,
                              triggered_at=datetime.now(timezone.utc),
                              auto_resume_after=auto_resume_after)
            self._events.append(event)
            return event

    def reset(self, scope: KillScope, target: str) -> None:
        with self._lock:
            self._events = [e for e in self._events if not (e.scope == scope and e.target == target)]

    def active(self) -> list[KillEvent]:
        with self._lock:
            now = datetime.now(timezone.utc)
            still_active: list[KillEvent] = []
            for e in self._events:
                if e.auto_resume_after is None:
                    still_active.append(e)
                elif now - e.triggered_at < e.auto_resume_after:
                    still_active.append(e)
            self._events = still_active
            return list(self._events)

    def is_tripped(self, scope: KillScope, target: str) -> bool:
        for e in self.active():
            if e.scope == scope and e.target == target:
                return True
            if e.scope is KillScope.PORTFOLIO and scope is not KillScope.PORTFOLIO:
                return True
        return False


# ─────────────────────────── pre-built switches ───────────────────────────

@dataclass
class LatencyTripper:
    """Trip when N consecutive orders exceed `threshold_ms`."""

    threshold_ms: float
    n_consecutive: int
    _consecutive: int = 0

    def observe(self, latency_ms: float) -> bool:
        if latency_ms > self.threshold_ms:
            self._consecutive += 1
        else:
            self._consecutive = 0
        return self._consecutive >= self.n_consecutive


@dataclass
class DrawdownTripper:
    """Trip when peak-to-current drawdown exceeds `threshold_pct`."""

    threshold_pct: float
    _peak: float = 0.0

    def observe(self, current_equity: float) -> bool:
        if current_equity > self._peak:
            self._peak = current_equity
        if self._peak <= 0:
            return False
        dd = (self._peak - current_equity) / self._peak
        return dd >= self.threshold_pct
