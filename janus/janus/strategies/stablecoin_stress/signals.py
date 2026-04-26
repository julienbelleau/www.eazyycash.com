"""Stablecoin Stress Flow signals.

Two layers:
  1. Stress event: depeg + volume anomaly + (optionally) issuer concern.
  2. Flow signal: BTC exchange inflows up + BTC/USDT volume share up +
     funding NOT already priced.

Both must pass for an entry. The 45-minute clock starts at stress detection;
if the flow signal hasn't fired by then, the trade is dead — by minute 46
the flow is arbitraged.
"""

from __future__ import annotations

from dataclasses import dataclass

from janus.features.stablecoin_features import (
    StablecoinSnapshot,
    btc_inflow_ratio,
    cex_dex_peg_arb_spread_bps,
    funding_already_priced,
    funding_term_structure,
    is_solvability_concern,
    pair_volume_ratio,
    peg_deviation_bps,
    pool_depth_severity,
    volume_anomaly_ratio,
)
from janus.strategies.base import Signal


@dataclass(frozen=True, slots=True)
class StressParams:
    peg_deviation_bps_min: float = 15.0           # 0.15%
    cex_deviation_bps_min: float = 10.0
    volume_ratio_min: float = 1.5
    require_solvability_concern: bool = False     # off by default — UPGRADES §3.2 informational


@dataclass(frozen=True, slots=True)
class FlowParams:
    inflow_ratio_min: float = 1.30
    pair_volume_ratio_min: float = 0.55
    funding_priced_blocks_signal: bool = True


def detect_stress_event(snapshot: StablecoinSnapshot, params: StressParams = StressParams()) -> Signal | None:
    dev_dex = peg_deviation_bps(snapshot, source="dex")
    dev_cex = peg_deviation_bps(snapshot, source="cex")
    vol_ratio = volume_anomaly_ratio(snapshot)

    if dev_dex < params.peg_deviation_bps_min and dev_cex < params.cex_deviation_bps_min:
        return None
    if vol_ratio < params.volume_ratio_min:
        return None

    if params.require_solvability_concern and is_solvability_concern(snapshot) is False:
        return None  # data present and benign → reject

    severity = pool_depth_severity(snapshot)
    arb_spread = cex_dex_peg_arb_spread_bps(snapshot)

    return Signal(
        name="stablecoin.stress_event",
        confidence=min(1.0, max(dev_dex, dev_cex) / 100.0),
        features={
            "peg_dev_dex_bps": dev_dex,
            "peg_dev_cex_bps": dev_cex,
            "volume_ratio": vol_ratio,
            "pool_depth_severity": severity,
            "cex_dex_spread_bps": arb_spread,
        },
        note=f"asset={snapshot.asset}",
    )


def detect_flow_signal(snapshot: StablecoinSnapshot, params: FlowParams = FlowParams()) -> Signal | None:
    inflow = btc_inflow_ratio(snapshot)
    if inflow < params.inflow_ratio_min:
        return None
    pvr = pair_volume_ratio(snapshot)
    if pvr < params.pair_volume_ratio_min:
        return None
    if params.funding_priced_blocks_signal and funding_already_priced(snapshot):
        return None

    fts = funding_term_structure(snapshot)
    return Signal(
        name="stablecoin.flow_signal",
        confidence=min(1.0, (inflow - 1.0) / 2.0 + 0.3),
        features={
            "btc_inflow_ratio": inflow,
            "pair_volume_ratio": pvr,
            "funding_slope_short": fts["slope_short"],
            "funding_slope_long": fts["slope_long"],
        },
        note=f"asset={snapshot.asset}",
    )
