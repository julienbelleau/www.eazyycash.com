"""BOCPD: confirm the run-length posterior collapses on synthetic mean shifts."""

from __future__ import annotations

import numpy as np

from janus.features.bocpd import Bocpd


def test_no_changepoint_in_iid_stream() -> None:
    """In a stationary stream, the MAP run length should grow ≈linearly."""
    b = Bocpd.make(hazard_lambda=500.0, mu0=0.0, kappa0=1.0, alpha0=1.0, beta0=1.0)
    rng = np.random.default_rng(0)
    for x in rng.normal(0, 1, size=300):
        b.update(float(x))
    # After 300 stationary obs, the MAP RL should be large (>50).
    assert b.run_length_map > 50


def test_changepoint_collapses_run_length() -> None:
    """A clear mean shift should collapse the MAP run length back near zero."""
    b = Bocpd.make(hazard_lambda=200.0, mu0=0.0, kappa0=1.0, alpha0=1.0, beta0=1.0)
    rng = np.random.default_rng(1)
    # Phase 1: stable around 0.
    for x in rng.normal(0, 1, size=200):
        b.update(float(x))
    pre_rl = b.run_length_map
    assert pre_rl > 30
    # Phase 2: strong shift to mean 10 — BOCPD should detect it.
    for x in rng.normal(10, 1, size=20):
        b.update(float(x))
    assert b.run_length_map < pre_rl, (
        "BOCPD should detect the mean shift and reset run length"
    )
    assert b.run_length_map < 25


def test_changepoint_probability_in_zero_one() -> None:
    b = Bocpd.make()
    for x in np.random.default_rng(2).normal(0, 1, size=50):
        b.update(float(x))
    assert 0.0 <= b.changepoint_probability <= 1.0
