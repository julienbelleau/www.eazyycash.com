"""Slippage models — L2 orderbook walk + sqrt-impact fallback.

Why this matters (UPGRADES §1.6 + plan §10):
- Backtest results are dominated by slippage assumptions. A naïve
  "0.05% on entry" hides cost in thin books, where a $1M order can move
  the mid by 30+ bps on midcap pairs.
- We support two models:
    * `OrderbookWalkSlippage`: walks the L2 snapshot at the order timestamp,
      filling the order against successive levels, returning the
      volume-weighted fill price. This is the realistic mode when L2 data
      exists in `orderbook_snapshots`.
    * `SquareRootImpactSlippage`: classical Almgren-Chriss-style impact:
      `slippage_bps = sigma * eta * sqrt(qty / ADV)`. Used when L2 data is
      absent or for symbols where L2 capture didn't run.

Both implement `fill(side, mark, qty, ctx) -> FillResult` so the engine
chooses based on data availability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class FillResult:
    fill_price: Decimal
    slippage_bps: float
    fully_filled: bool


class SlippageModel(Protocol):
    def fill(self, *, side: str, mark: Decimal, qty: Decimal,
             ctx: dict[str, Any]) -> FillResult: ...


@dataclass(frozen=True, slots=True)
class OrderbookWalkSlippage:
    """Walk an L2 snapshot to determine the fill price.

    `ctx` must carry `bids` and `asks` lists of `[price, qty]` tuples,
    sorted respectively descending and ascending — matching the format
    stored in `orderbook_snapshots`.
    """

    fee_bps: float = 4.0  # Binance VIP-0 taker

    def fill(self, *, side: str, mark: Decimal, qty: Decimal,
             ctx: dict[str, Any]) -> FillResult:
        levels = ctx.get("asks" if side == "long" else "bids", [])
        if not levels:
            # No book — return mark + worst-case 50 bps slippage.
            slip = Decimal("0.0050")
            return FillResult(mark * (Decimal(1) + slip if side == "long" else Decimal(1) - slip),
                              50.0, True)

        remaining = qty
        cost = Decimal(0)
        filled = Decimal(0)
        for level in levels:
            price = Decimal(str(level[0]))
            available = Decimal(str(level[1]))
            take = min(remaining, available)
            cost += price * take
            filled += take
            remaining -= take
            if remaining <= 0:
                break

        if filled == 0:
            return FillResult(mark, 0.0, False)
        avg = cost / filled
        bps = float((avg - mark) / mark * Decimal(10_000)) if side == "long" \
              else float((mark - avg) / mark * Decimal(10_000))
        # Fees compound on top of book impact.
        bps += self.fee_bps
        adj = avg * (Decimal(1) + Decimal(str(self.fee_bps / 10_000))) if side == "long" \
              else avg * (Decimal(1) - Decimal(str(self.fee_bps / 10_000)))
        return FillResult(adj, bps, remaining <= 0)


@dataclass(frozen=True, slots=True)
class SquareRootImpactSlippage:
    """Classical sqrt-law market impact (Almgren-Chriss).

    `slippage_bps = eta * sigma_intraday * sqrt(qty / adv)` × 10000.
    Defaults are calibrated to BTC midcaps; override per-symbol in production.
    """

    eta: float = 0.5
    sigma_intraday: float = 0.02     # 2% intraday vol baseline
    fee_bps: float = 4.0
    adv_quote: float = 50_000_000.0  # default $50M ADV

    def fill(self, *, side: str, mark: Decimal, qty: Decimal,
             ctx: dict[str, Any]) -> FillResult:
        adv = float(ctx.get("adv_quote", self.adv_quote))
        notional = float(qty) * float(mark)
        if adv <= 0:
            adv = self.adv_quote
        impact = self.eta * self.sigma_intraday * math.sqrt(max(notional / adv, 0.0))
        bps = impact * 10_000 + self.fee_bps
        slip = Decimal(str(bps / 10_000))
        sign = Decimal(1) if side == "long" else Decimal(-1)
        return FillResult(mark * (Decimal(1) + sign * slip), bps, True)
