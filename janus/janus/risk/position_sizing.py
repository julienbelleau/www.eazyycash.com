"""Position sizing — fractional Kelly + volatility overlay + caps.

Plan §8 specifies quart-Kelly sized off backtest win-rate / win-loss ratio,
plus 10% per-trade and 25% per-strategy caps. This module implements that and
adds the UPGRADES §R.1 volatility overlay (target portfolio σ = 15% annualised).

Sizing pipeline:
  1. Compute raw Kelly fraction from (win_rate, avg_win, avg_loss).
  2. Apply Kelly fraction multiplier (default 0.25 — quart-Kelly).
  3. Rescale by σ_target / σ_realised (vol overlay).
  4. Clip to per-trade cap (10% of portfolio) and per-strategy cap (25%).

All inputs are pure functions of *backtest stats + current portfolio state*;
no I/O. The caller (engine) is responsible for plugging the right values in.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StrategyEdge:
    """Backtest summary stats used to compute Kelly."""

    win_rate: float       # in (0, 1)
    avg_win_pct: float    # average win as fraction of risked capital
    avg_loss_pct: float   # average loss (positive number)


@dataclass(frozen=True, slots=True)
class SizingPolicy:
    kelly_fraction: float = 0.25            # quart-Kelly default
    per_trade_cap_pct: float = 10.0
    per_strategy_cap_pct: float = 25.0
    sigma_target_annual: float = 0.15       # 15% target vol
    min_sigma_floor: float = 0.05           # never divide by tiny σ
    max_overlay_multiplier: float = 2.0     # cap on the σ_target / σ_realised lever


def kelly_fraction(edge: StrategyEdge) -> float:
    """Full-Kelly fraction. Returns 0 if the edge is negative or stats invalid."""
    if not 0.0 < edge.win_rate < 1.0:
        return 0.0
    if edge.avg_win_pct <= 0 or edge.avg_loss_pct <= 0:
        return 0.0
    win_loss_ratio = edge.avg_win_pct / edge.avg_loss_pct
    f = edge.win_rate - (1.0 - edge.win_rate) / win_loss_ratio
    return max(0.0, f)


def vol_overlay_multiplier(
    realised_sigma_annual: float,
    target_sigma_annual: float,
    *,
    min_sigma_floor: float = 0.05,
    max_multiplier: float = 2.0,
) -> float:
    """Multiplier to rescale a position to a target portfolio volatility.

    Capped above by `max_multiplier` to prevent a low-vol regime from levering
    the portfolio to dangerous levels.
    """
    sigma = max(realised_sigma_annual, min_sigma_floor)
    raw = target_sigma_annual / sigma
    return min(raw, max_multiplier)


def position_size_quote(
    *,
    portfolio_quote: Decimal,
    edge: StrategyEdge,
    realised_sigma_annual: float,
    policy: SizingPolicy = SizingPolicy(),
    current_strategy_exposure_pct: float = 0.0,
) -> Decimal:
    """Return the recommended position size in quote currency for a single trade."""
    kf = kelly_fraction(edge)
    if kf == 0.0:
        return Decimal(0)

    fkelly = kf * policy.kelly_fraction
    overlay = vol_overlay_multiplier(
        realised_sigma_annual,
        policy.sigma_target_annual,
        min_sigma_floor=policy.min_sigma_floor,
        max_multiplier=policy.max_overlay_multiplier,
    )
    raw_pct = fkelly * overlay * 100.0  # express as percent of portfolio

    # Per-trade cap.
    raw_pct = min(raw_pct, policy.per_trade_cap_pct)

    # Per-strategy cap (account for already-open exposure in the same strategy).
    headroom_pct = max(0.0, policy.per_strategy_cap_pct - current_strategy_exposure_pct)
    raw_pct = min(raw_pct, headroom_pct)

    if raw_pct <= 0:
        return Decimal(0)

    return portfolio_quote * Decimal(str(raw_pct / 100.0))
