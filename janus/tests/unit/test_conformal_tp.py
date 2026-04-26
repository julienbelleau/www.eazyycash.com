"""Split-conformal regressor tests."""

from __future__ import annotations

import numpy as np
import pytest

from janus.features.conformal_tp import SplitConformal


def test_fit_requires_minimum_samples() -> None:
    cal = SplitConformal()
    with pytest.raises(ValueError, match="at least 20"):
        cal.fit(predicted=[0.5] * 5, observed=[0.6] * 5)


def test_fit_requires_equal_lengths() -> None:
    cal = SplitConformal()
    with pytest.raises(ValueError, match="equal length"):
        cal.fit(predicted=[0.5] * 30, observed=[0.6] * 29)


def test_predict_interval_widens_with_lower_alpha() -> None:
    rng = np.random.default_rng(0)
    pred = rng.uniform(0, 1, size=200)
    obs = pred + rng.normal(0, 0.1, size=200)
    cal = SplitConformal()
    cal.fit(predicted=pred, observed=obs)

    iv_90 = cal.predict_interval(0.5, alpha=0.10)
    iv_99 = cal.predict_interval(0.5, alpha=0.01)
    # Wider coverage target → wider interval.
    assert (iv_99.upper - iv_99.lower) > (iv_90.upper - iv_90.lower)


def test_empirical_coverage_close_to_target() -> None:
    rng = np.random.default_rng(7)
    pred_cal = np.full(500, 0.5)
    obs_cal = 0.5 + rng.normal(0, 0.1, size=500)
    cal = SplitConformal()
    cal.fit(predicted=pred_cal, observed=obs_cal)

    # Held-out observations from the same DGP.
    held = 0.5 + rng.normal(0, 0.1, size=2000)
    coverage = cal.empirical_coverage(0.5, alpha=0.10, new_observed=held)
    # Should be ~ 0.90 ± 0.03.
    assert 0.85 <= coverage <= 0.95


def test_alpha_bounds() -> None:
    cal = SplitConformal()
    cal.fit(predicted=[0.5] * 30, observed=[0.6] * 30)
    with pytest.raises(ValueError, match="alpha"):
        cal.predict_interval(0.5, alpha=0.0)
    with pytest.raises(ValueError, match="alpha"):
        cal.predict_interval(0.5, alpha=1.0)
