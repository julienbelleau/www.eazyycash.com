"""Drawdown management — soft cap, hard cap, portfolio kill (plan §8)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrawdownAction:
    multiplier: float           # apply to position size (0 = stop trading)
    disarm_for_days: int = 0    # hard-cap penalty
    halt_portfolio: bool = False


@dataclass
class DrawdownManager:
    soft_cap_pct: float = 10.0
    hard_cap_pct: float = 15.0
    portfolio_halt_pct: float = 20.0
    _peak: float = 0.0
    _peak_per_strat: dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._peak_per_strat = {}

    def update_strategy(self, strategy_id: str, current_equity: float) -> DrawdownAction:
        peak = self._peak_per_strat.get(strategy_id, current_equity)
        if current_equity > peak:
            peak = current_equity
            self._peak_per_strat[strategy_id] = peak
            return DrawdownAction(multiplier=1.0)
        self._peak_per_strat[strategy_id] = peak
        if peak <= 0:
            return DrawdownAction(multiplier=1.0)
        dd = (peak - current_equity) / peak * 100.0

        if dd >= self.hard_cap_pct:
            return DrawdownAction(multiplier=0.0, disarm_for_days=30)
        if dd >= self.soft_cap_pct:
            return DrawdownAction(multiplier=0.5)
        return DrawdownAction(multiplier=1.0)

    def update_portfolio(self, current_equity: float) -> DrawdownAction:
        if current_equity > self._peak:
            self._peak = current_equity
        if self._peak <= 0:
            return DrawdownAction(multiplier=1.0)
        dd = (self._peak - current_equity) / self._peak * 100.0
        if dd >= self.portfolio_halt_pct:
            return DrawdownAction(multiplier=0.0, halt_portfolio=True)
        return DrawdownAction(multiplier=1.0)
