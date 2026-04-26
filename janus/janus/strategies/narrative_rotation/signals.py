"""Narrative-rotation signals.

Two signals:
  1. Leader decelerating: the current top-momentum narrative shows
     consistently negative acceleration (UPGRADES §2.2 — uses the smoothed EMA
     to suppress single-day noise).
  2. Emergent rotation candidate: a non-leader narrative shows
     positive-and-growing acceleration AND a momentum rank in the 2-5 band
     AND BTC dominance is stable/declining (proxy for altseason).

These signals are computed from the per-narrative DataFrame produced by
`features.narrative_index`.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from janus.strategies.base import Signal


@dataclass(frozen=True, slots=True)
class RotationParams:
    leader_window_days: int = 30
    decel_consecutive_days: int = 5
    emergent_rank_min: int = 2
    emergent_rank_max: int = 5
    btc_dom_max_change_14d_pct: float = 0.0     # require neg or stable
    use_excess_returns: bool = True              # UPGRADES §2.3


def _latest_per_narrative(df: pl.DataFrame, as_of: pl.Date) -> pl.DataFrame:
    return (
        df.filter(pl.col("date") <= as_of)
        .sort("date")
        .group_by("narrative")
        .last()
    )


def detect_leader_deceleration(
    feature_df: pl.DataFrame, *, as_of: pl.Date, params: RotationParams = RotationParams(),
) -> Signal | None:
    """Returns a signal if the current leader has been decelerating for N consecutive days."""
    latest = _latest_per_narrative(feature_df, as_of)
    if latest.is_empty():
        return None
    mom_col = "momentum"
    if params.use_excess_returns and "excess_ret" in feature_df.columns:
        mom_col = "momentum"  # momentum is computed off ret regardless; rerunner can swap.
    leader = latest.sort(mom_col, descending=True).head(1)
    if leader.is_empty():
        return None
    leader_narr = str(leader.get_column("narrative")[0])

    # Last N days of acceleration for the leader.
    leader_hist = (
        feature_df.filter(pl.col("narrative") == leader_narr)
        .filter(pl.col("date") <= as_of)
        .sort("date")
        .tail(params.decel_consecutive_days)
    )
    if leader_hist.height < params.decel_consecutive_days:
        return None
    accels = leader_hist.get_column("acceleration").to_list()
    if not all(a < 0 for a in accels):
        return None

    return Signal(
        name="narrative.leader_decelerating",
        confidence=0.6,
        features={
            "leader": hash(leader_narr) % 1_000_000,  # int proxy for log
            "min_accel": min(accels),
            "max_accel": max(accels),
        },
        note=f"leader={leader_narr}",
    )


def find_emergent_rotation(
    feature_df: pl.DataFrame, *, as_of: pl.Date,
    btc_dom_change_14d_pct: float,
    params: RotationParams = RotationParams(),
) -> Signal | None:
    """Returns a signal naming the emergent narrative if rotation conditions hold."""
    if btc_dom_change_14d_pct > params.btc_dom_max_change_14d_pct:
        return None

    latest = _latest_per_narrative(feature_df, as_of)
    if latest.is_empty():
        return None
    ranked = latest.sort("momentum", descending=True)
    candidates = ranked.slice(params.emergent_rank_min - 1,
                              params.emergent_rank_max - params.emergent_rank_min + 1)
    if candidates.is_empty():
        return None

    # Among candidates, require positive AND growing acceleration in the last 3 days.
    best: tuple[str, float] | None = None
    for row in candidates.iter_rows(named=True):
        narr = row["narrative"]
        recent = (
            feature_df.filter(pl.col("narrative") == narr)
            .filter(pl.col("date") <= as_of)
            .sort("date")
            .tail(3)
        )
        if recent.height < 3:
            continue
        accels = recent.get_column("acceleration").to_list()
        if not all(a > 0 for a in accels):
            continue
        if not (accels[-1] > accels[-2] > accels[-3]):
            continue
        score = float(accels[-1])
        if best is None or score > best[1]:
            best = (narr, score)

    if best is None:
        return None

    return Signal(
        name="narrative.emergent",
        confidence=min(1.0, best[1] * 100),  # rough scaling — tuned in Phase 2 calibration
        features={"acceleration": best[1], "btc_dom_change_14d_pct": btc_dom_change_14d_pct},
        note=f"emergent={best[0]}",
    )
