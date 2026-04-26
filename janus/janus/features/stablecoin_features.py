"""Stablecoin stress / flow features.

Computed point-in-time from a `StablecoinSnapshot` containing the inputs
the strategy needs: peg deviations across DEX/CEX, supply changes, BTC
exchange inflows, BTC pair-volume ratios, and funding term structure.

Pro-tier upgrades (UPGRADES §3.1-§3.4):
- 3.1 pool_depth_at_peg(): TVL on the depeg side of a Curve/Uniswap pool.
       A 0.15% depeg in $5M pool ≠ same depeg in $500M pool — depth scales
       the urgency of the flow signal.
- 3.2 issuer_treasury_ratio(): cash-equivalents / total liabilities. Used to
       distinguish solvability-driven (slow, deep) vs liquidity-driven (fast,
       shallow) depegs.
- 3.3 cex_dex_peg_arb_spread(): difference between CEX bid and DEX mid for
       the stablecoin/USD pair. Capture the route capital is fleeing through.
- 3.4 funding_term_structure(): funding-rate slope over 1h/8h/24h horizons.
       If perps already priced the flow, our spot edge is reduced.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class StablecoinSnapshot:
    asset: str                                  # USDT, USDC, DAI
    as_of: datetime
    cex_price_usd: Decimal                       # e.g. Binance USDC/USDT mid
    dex_price_usd: Decimal                       # e.g. Curve 3pool USDC/USDT
    pool_depth_usd: Decimal                      # TVL on the depeg side
    issuer_cash_equivalents_usd: Decimal | None
    issuer_total_liabilities_usd: Decimal | None
    cex_volume_24h_usd: Decimal
    cex_volume_24h_baseline: Decimal             # 7-day mean
    btc_exchange_inflow_btc: Decimal             # past 1h
    btc_exchange_inflow_baseline: Decimal        # 7-day mean
    btc_pair_volume_btcusdt: Decimal             # past 1h
    btc_pair_volume_btcusdc: Decimal
    funding_1h: Decimal
    funding_8h: Decimal
    funding_24h: Decimal


def peg_deviation_bps(snapshot: StablecoinSnapshot, *, source: str = "dex") -> float:
    price = snapshot.dex_price_usd if source == "dex" else snapshot.cex_price_usd
    return float(abs(price - Decimal(1)) / Decimal(1) * Decimal(10_000))


def cex_dex_peg_arb_spread_bps(snapshot: StablecoinSnapshot) -> float:
    """UPGRADES §3.3 — difference between CEX and DEX prints in bps."""
    diff = snapshot.cex_price_usd - snapshot.dex_price_usd
    if snapshot.cex_price_usd == 0:
        return 0.0
    return float(diff / snapshot.cex_price_usd * Decimal(10_000))


def pool_depth_severity(snapshot: StablecoinSnapshot, *, reference_depth_usd: Decimal = Decimal("500000000")) -> float:
    """Returns 0-1 severity multiplier — thinner pool ⇒ more urgent flow.

    Severity = 1.0 when pool depth equals reference; >1 when shallower.
    Capped at 5.0 to avoid runaway sizing in a tiny-pool flash event.
    """
    if snapshot.pool_depth_usd <= 0:
        return 5.0
    raw = float(reference_depth_usd / snapshot.pool_depth_usd)
    return max(0.0, min(raw, 5.0))


def issuer_treasury_ratio(snapshot: StablecoinSnapshot) -> float | None:
    """Cash-equivalents / liabilities. None if data unavailable."""
    if snapshot.issuer_cash_equivalents_usd is None or snapshot.issuer_total_liabilities_usd is None:
        return None
    if snapshot.issuer_total_liabilities_usd <= 0:
        return None
    return float(snapshot.issuer_cash_equivalents_usd / snapshot.issuer_total_liabilities_usd)


def is_solvability_concern(snapshot: StablecoinSnapshot, *, threshold: float = 1.02) -> bool | None:
    """True iff the issuer's cash-eq is below 102% of liabilities.

    Returns None when data isn't available — caller decides on default.
    """
    ratio = issuer_treasury_ratio(snapshot)
    if ratio is None:
        return None
    return ratio < threshold


def volume_anomaly_ratio(snapshot: StablecoinSnapshot) -> float:
    if snapshot.cex_volume_24h_baseline <= 0:
        return 0.0
    return float(snapshot.cex_volume_24h_usd / snapshot.cex_volume_24h_baseline)


def btc_inflow_ratio(snapshot: StablecoinSnapshot) -> float:
    if snapshot.btc_exchange_inflow_baseline <= 0:
        return 0.0
    return float(snapshot.btc_exchange_inflow_btc / snapshot.btc_exchange_inflow_baseline)


def pair_volume_ratio(snapshot: StablecoinSnapshot) -> float:
    """Volume share of BTCUSDT vs BTCUSDC — when USDC is the stressed coin
    we expect BTCUSDT volume to surge relative to BTCUSDC.
    """
    total = snapshot.btc_pair_volume_btcusdt + snapshot.btc_pair_volume_btcusdc
    if total == 0:
        return 0.5
    return float(snapshot.btc_pair_volume_btcusdt / total)


def funding_term_structure(snapshot: StablecoinSnapshot) -> dict[str, float]:
    """UPGRADES §3.4. Slopes describe how aggressively perps are pricing flow."""
    f1, f8, f24 = float(snapshot.funding_1h), float(snapshot.funding_8h), float(snapshot.funding_24h)
    return {
        "level_1h": f1, "level_8h": f8, "level_24h": f24,
        "slope_short": f8 - f1,
        "slope_long": f24 - f8,
    }


def funding_already_priced(snapshot: StablecoinSnapshot, *, slope_threshold: float = 1e-4) -> bool:
    """True iff the funding term structure is steeply positive — perps have
    already priced the flow we'd want to capture, so the spot edge is reduced.
    """
    ts = funding_term_structure(snapshot)
    return ts["slope_short"] > slope_threshold and ts["slope_long"] > slope_threshold
