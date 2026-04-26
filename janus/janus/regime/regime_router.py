"""Regime → which strategies are armed.

Per the plan §7, regime gating *picks* which strategy gets to act on its own
signals. The router does NOT combine signals across strategies — that's the
engine's job.

Confidence-weighted gating (UPGRADES §4.3): rather than a binary "armed /
disarmed", the router returns a weight in [0, 1] per strategy. The risk
overlay multiplies the strategy's notional by this weight. A weight of 0
fully disarms; a weight of 0.5 means "trade at half size".

Counterfactual evaluation (UPGRADES §4.4) is supported via `evaluate_counter()`
which returns what each strategy *would* have traded if always-armed — used
by the daily report to measure the gating layer's edge in real-time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from janus.regime.hmm_detector import Regime


class StrategyId(StrEnum):
    REFRACTORY = "refractory_v1"
    NARRATIVE = "narrative_rotation_v1"
    STABLECOIN = "stablecoin_stress_v1"


# Plan §7 mapping — translated to confidence weights.
# "armée (forte prob)" → 1.0
# "armée"               → 0.7
# "armée (faible prob)" → 0.5
# "désarmée"            → 0.0
_BASE_WEIGHTS: Mapping[Regime, dict[StrategyId, float]] = {
    Regime.TRENDING_BULL: {
        StrategyId.REFRACTORY: 0.5, StrategyId.NARRATIVE: 1.0, StrategyId.STABLECOIN: 0.7,
    },
    Regime.TRENDING_BEAR: {
        StrategyId.REFRACTORY: 1.0, StrategyId.NARRATIVE: 0.0, StrategyId.STABLECOIN: 0.7,
    },
    Regime.RANGE: {
        StrategyId.REFRACTORY: 0.0, StrategyId.NARRATIVE: 0.0, StrategyId.STABLECOIN: 0.7,
    },
    Regime.CRISIS: {
        StrategyId.REFRACTORY: 1.0, StrategyId.NARRATIVE: 0.0, StrategyId.STABLECOIN: 1.0,
    },
    Regime.RECOVERY: {
        StrategyId.REFRACTORY: 0.7, StrategyId.NARRATIVE: 0.7, StrategyId.STABLECOIN: 0.7,
    },
}


@dataclass(frozen=True, slots=True)
class GatingDecision:
    regime: Regime
    weights: dict[StrategyId, float]
    transition_dampener: float       # in [0, 1] applied during BOCPD-flagged transitions

    def weight_for(self, strategy: StrategyId) -> float:
        return self.weights.get(strategy, 0.0) * self.transition_dampener


def gate(
    regime: Regime,
    *,
    is_transitioning: bool = False,
    transition_dampener: float = 0.5,
    confidence: float = 1.0,
) -> GatingDecision:
    """Compute the gating decision.

    `confidence`: the HMM posterior of the chosen regime in [0, 1]. We
    multiply each base weight by this — UPGRADES §4.3.
    `is_transitioning`: from BOCPDRegimeTransitionDetector.is_transitioning.
    During a transition we dampen all weights to avoid over-trading the pivot.
    """
    base = dict(_BASE_WEIGHTS[regime])
    weights = {sid: w * confidence for sid, w in base.items()}
    dampener = transition_dampener if is_transitioning else 1.0
    return GatingDecision(
        regime=regime, weights=weights, transition_dampener=dampener,
    )


def evaluate_counter(weights: Mapping[StrategyId, float]) -> Mapping[StrategyId, float]:
    """Return the always-armed counterfactual weights (all 1.0).

    Daily report compares actual P&L (gated) vs counterfactual P&L (always
    armed) to measure the gating layer's edge — UPGRADES §4.4.
    """
    return {sid: 1.0 for sid in weights}
