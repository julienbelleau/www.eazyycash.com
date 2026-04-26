"""Smart order router.

V1 logic (plan §9):
1. For positions over `large_position_quote`, split into N child orders
   spread over `slice_minutes` (TWAP-equivalent).
2. For each child:
   - Submit a limit order at mid ± one tick (capture maker rebate).
   - If unfilled after `limit_timeout_s`, cancel and resubmit as market
     IFF the signal is still considered valid (caller passes a predicate).

Almgren-Chriss-style optimal sizing (UPGRADES §E.1) is captured in the
`almgren_chriss_schedule()` helper — the smart router can opt into using
that instead of naïve TWAP for large positions.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RoutingPolicy:
    large_position_quote: Decimal = Decimal("10000")
    slice_count_default: int = 4
    slice_minutes_default: int = 10
    limit_timeout_s: int = 60
    market_fallback_enabled: bool = True


def naive_twap_schedule(
    total_qty: Decimal, *, n_slices: int, minutes_total: int,
) -> list[tuple[Decimal, int]]:
    """Equal-size, equal-spaced child orders. Returns (qty, minute_offset) pairs."""
    if n_slices < 1:
        return []
    per = total_qty / Decimal(n_slices)
    spacing = max(1, minutes_total // n_slices)
    return [(per, i * spacing) for i in range(n_slices)]


def almgren_chriss_schedule(
    total_qty: Decimal, *, n_slices: int, minutes_total: int,
    sigma: float = 0.02, eta: float = 0.5, lambda_: float = 1e-6,
) -> list[tuple[Decimal, int]]:
    """Almgren-Chriss optimal liquidation schedule (constant participation rate).

    For risk-neutral execution (lambda_ → 0), the schedule degenerates to
    TWAP. For risk-averse (lambda_ > 0), it's front-loaded: liquidate faster
    when impact is lower than expected risk cost.

    This is the closed-form solution for a constant-temporary-impact model
    with linear permanent impact ignored. Sufficient for our backtest.
    """
    if n_slices < 1:
        return []
    qty = float(total_qty)
    kappa_sq = lambda_ * sigma * sigma / eta
    kappa = math.sqrt(max(kappa_sq, 1e-12))
    T = max(minutes_total, 1)
    step_minutes = T / n_slices
    schedule: list[tuple[Decimal, int]] = []
    prev_remaining = qty
    for i in range(1, n_slices + 1):
        t = i * step_minutes
        remaining = qty * math.sinh(kappa * (T - t)) / math.sinh(kappa * T) \
            if kappa * T > 0 else qty * (1 - i / n_slices)
        remaining = max(0.0, remaining)
        slice_qty = max(0.0, prev_remaining - remaining)
        schedule.append((Decimal(str(slice_qty)), int((i - 1) * step_minutes)))
        prev_remaining = remaining
    return schedule


def should_split(notional_quote: Decimal, policy: RoutingPolicy = RoutingPolicy()) -> bool:
    return notional_quote > policy.large_position_quote


def schedule_for(
    total_qty: Decimal, *, mark: Decimal,
    use_almgren_chriss: bool = False,
    sigma: float = 0.02, eta: float = 0.5, lambda_: float = 1e-6,
    policy: RoutingPolicy = RoutingPolicy(),
) -> list[tuple[Decimal, int]]:
    notional = total_qty * mark
    if not should_split(notional, policy):
        return [(total_qty, 0)]
    if use_almgren_chriss:
        return almgren_chriss_schedule(
            total_qty, n_slices=policy.slice_count_default,
            minutes_total=policy.slice_minutes_default,
            sigma=sigma, eta=eta, lambda_=lambda_,
        )
    return naive_twap_schedule(
        total_qty, n_slices=policy.slice_count_default,
        minutes_total=policy.slice_minutes_default,
    )
