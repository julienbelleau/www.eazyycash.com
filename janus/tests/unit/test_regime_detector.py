"""HMM regime detector + BOCPD transition + router + macro features tests."""

from __future__ import annotations

import numpy as np
import pytest

from janus.regime.bocpd_regime import BocpdRegimeTransitionDetector, vol_of_vol
from janus.regime.hmm_detector import HmmRegimeDetector, Regime
from janus.regime.macro_features import MacroPanel, append_macro_to_features, macro_log_returns
from janus.regime.regime_router import (
    GatingDecision,
    StrategyId,
    evaluate_counter,
    gate,
)


# ─── HMM detector ───

def _make_synthetic_features(n: int = 1000, seed: int = 0) -> np.ndarray:
    """3 regimes encoded as Gaussian clusters in a (return, vol) space."""
    rng = np.random.default_rng(seed)
    # 1/3 bull, 1/3 bear, 1/3 crisis.
    third = n // 3
    bull = np.column_stack([rng.normal(0.5, 0.1, third), rng.normal(0.2, 0.05, third)])
    bear = np.column_stack([rng.normal(-0.3, 0.1, third), rng.normal(0.4, 0.05, third)])
    crisis = np.column_stack([rng.normal(-1.0, 0.2, third), rng.normal(1.5, 0.2, third)])
    return np.vstack([bull, bear, crisis])


def test_hmm_fit_and_classify() -> None:
    pytest.importorskip("hmmlearn")
    X = _make_synthetic_features(n=900, seed=1)
    det = HmmRegimeDetector(n_states=5, smoothing_window=3)
    det.fit(X)
    regimes = det.classify(X)
    assert len(regimes) == X.shape[0]
    # Should see at least 3 distinct regimes in the output.
    distinct = set(regimes)
    assert len(distinct) >= 3


def test_hmm_rejects_too_few_samples() -> None:
    pytest.importorskip("hmmlearn")
    det = HmmRegimeDetector(n_states=5)
    with pytest.raises(ValueError, match="at least"):
        det.fit(np.zeros((10, 2)))


def test_hmm_state_to_regime_assigned() -> None:
    pytest.importorskip("hmmlearn")
    X = _make_synthetic_features()
    det = HmmRegimeDetector(n_states=5)
    det.fit(X)
    # All 5 states must be mapped to a Regime.
    assert len(det.state_to_regime) == 5
    assert all(isinstance(v, Regime) for v in det.state_to_regime.values())


# ─── BOCPD transition ───

def test_vol_of_vol_zero_on_short_input() -> None:
    assert vol_of_vol(np.array([1.0, 2.0, 3.0])) == 0.0


def test_bocpd_regime_detects_transition() -> None:
    det = BocpdRegimeTransitionDetector.make()
    rng = np.random.default_rng(0)
    # Stable phase
    for _ in range(200):
        det.update(float(abs(rng.normal(0, 0.01))))
    pre_rl = det.bocpd.run_length_map
    # Volatile-of-volatile shock
    for _ in range(15):
        det.update(float(abs(rng.normal(0, 0.5))))
    assert det.bocpd.run_length_map < pre_rl


def test_bocpd_regime_transition_probability_bounds() -> None:
    det = BocpdRegimeTransitionDetector.make()
    for x in np.random.default_rng(0).uniform(0, 0.1, size=50):
        det.update(float(x))
    assert 0.0 <= det.transition_probability <= 1.0


# ─── Router ───

def test_gate_disarms_narrative_in_range() -> None:
    decision = gate(Regime.RANGE)
    assert decision.weight_for(StrategyId.NARRATIVE) == 0.0
    assert decision.weight_for(StrategyId.STABLECOIN) > 0


def test_gate_arms_refractory_in_crisis() -> None:
    decision = gate(Regime.CRISIS, confidence=1.0)
    assert decision.weight_for(StrategyId.REFRACTORY) == 1.0
    assert decision.weight_for(StrategyId.STABLECOIN) == 1.0


def test_gate_dampens_during_transition() -> None:
    a = gate(Regime.CRISIS, is_transitioning=False)
    b = gate(Regime.CRISIS, is_transitioning=True, transition_dampener=0.5)
    assert b.weight_for(StrategyId.REFRACTORY) == a.weight_for(StrategyId.REFRACTORY) * 0.5


def test_gate_scales_with_confidence() -> None:
    high = gate(Regime.TRENDING_BULL, confidence=1.0)
    low = gate(Regime.TRENDING_BULL, confidence=0.5)
    assert low.weight_for(StrategyId.NARRATIVE) == 0.5
    assert high.weight_for(StrategyId.NARRATIVE) == 1.0


def test_evaluate_counter_returns_unit_weights() -> None:
    decision = gate(Regime.CRISIS)
    counter = evaluate_counter(decision.weights)
    assert all(v == 1.0 for v in counter.values())


# ─── Macro features ───

def test_macro_log_returns_shapes() -> None:
    n = 30
    panel = MacroPanel(
        dates=np.array([None] * n),
        dxy=np.linspace(100, 110, n),
        vix=np.linspace(15, 25, n),
        us10y=np.linspace(3.5, 4.0, n),
        gold=np.linspace(1800, 1900, n),
        sp500=np.linspace(4000, 4500, n),
    )
    rets = macro_log_returns(panel)
    assert all(len(v) == n - 1 for v in rets.values())


def test_append_macro_concatenates() -> None:
    n = 50
    panel = MacroPanel(
        dates=np.array([None] * n),
        dxy=np.linspace(100, 110, n),
        vix=np.linspace(15, 25, n),
        us10y=np.linspace(3.5, 4.0, n),
        gold=np.linspace(1800, 1900, n),
        sp500=np.linspace(4000, 4500, n),
    )
    fm = np.random.default_rng(0).standard_normal((n, 3))
    result = append_macro_to_features(fm, panel)
    # Original 3 cols + 5 macro cols = 8 cols. n-1 rows due to log returns.
    assert result.shape[1] == 8
    assert result.shape[0] == n - 1
