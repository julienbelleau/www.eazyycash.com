"""P² online quantile estimator tests.

Property: after enough samples from a known distribution, the estimate must
be within tolerance of the true quantile.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.features.adaptive_thresholds import P2Quantile, RollingQuantile


def test_warmup_returns_nan() -> None:
    q = P2Quantile.make(0.5)
    for x in (1.0, 2.0, 3.0):
        q.update(x)
    assert not q.is_warm
    assert np.isnan(q.value)


def test_median_of_uniform() -> None:
    q = P2Quantile.make(0.5)
    rng = np.random.default_rng(42)
    for x in rng.uniform(0, 1, size=10_000):
        q.update(float(x))
    assert q.is_warm
    assert abs(q.value - 0.5) < 0.02


def test_p95_of_normal() -> None:
    q = P2Quantile.make(0.95)
    rng = np.random.default_rng(7)
    samples = rng.normal(loc=0.0, scale=1.0, size=20_000)
    for x in samples:
        q.update(float(x))
    true = np.quantile(samples, 0.95)
    # P² guarantees ~1% error after enough samples for moderate quantiles.
    assert abs(q.value - true) < 0.05


def test_invalid_p_rejected() -> None:
    with pytest.raises(ValueError):
        P2Quantile.make(0.0)
    with pytest.raises(ValueError):
        P2Quantile.make(1.0)


def test_rolling_quantile_warmup_gate() -> None:
    rq = RollingQuantile.make(0.95, min_warmup=100)
    rq.feed(1.0)
    assert rq.threshold() is None
    assert not rq.is_above(1e9)
    rng = np.random.default_rng(1)
    for x in rng.normal(0, 1, size=200):
        rq.feed(float(x))
    assert rq.threshold() is not None
    assert rq.is_above(10.0)
    assert not rq.is_above(-10.0)


@given(
    st.lists(st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
             min_size=200, max_size=2000),
    st.floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=20, deadline=None)
def test_p2_within_tolerance_property(xs: list[float], p: float) -> None:
    q = P2Quantile.make(p)
    for x in xs:
        q.update(x)
    true = float(np.quantile(xs, p))
    spread = max(xs) - min(xs)
    # Tolerance scales with the dynamic range of the input.
    assert abs(q.value - true) <= 0.10 * spread + 0.5
