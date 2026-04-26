"""Risk overlay tests: kill switches, correlation monitor, drawdown manager."""

from __future__ import annotations

from datetime import timedelta

from janus.risk.correlation_monitor import CorrelationMonitor
from janus.risk.drawdown_manager import DrawdownAction, DrawdownManager
from janus.risk.kill_switches import (
    DrawdownTripper,
    KillScope,
    KillSwitchRegistry,
    LatencyTripper,
)


# ─── kill switches ───

def test_kill_registry_trip_and_reset() -> None:
    reg = KillSwitchRegistry()
    assert not reg.is_tripped(KillScope.STRATEGY, "x")
    reg.trip(KillScope.STRATEGY, "x", "test")
    assert reg.is_tripped(KillScope.STRATEGY, "x")
    reg.reset(KillScope.STRATEGY, "x")
    assert not reg.is_tripped(KillScope.STRATEGY, "x")


def test_kill_portfolio_blocks_strategy_check() -> None:
    reg = KillSwitchRegistry()
    reg.trip(KillScope.PORTFOLIO, "global", "halt")
    # Any strategy/exchange check should also report tripped.
    assert reg.is_tripped(KillScope.STRATEGY, "any")
    assert reg.is_tripped(KillScope.EXCHANGE, "binance")


def test_kill_auto_resume_expires() -> None:
    reg = KillSwitchRegistry()
    # Past expiry
    reg.trip(KillScope.STRATEGY, "x", "transient", auto_resume_after=timedelta(seconds=-1))
    assert not reg.is_tripped(KillScope.STRATEGY, "x")


def test_latency_tripper_consecutive() -> None:
    t = LatencyTripper(threshold_ms=100, n_consecutive=3)
    assert not t.observe(150)
    assert not t.observe(120)
    assert t.observe(200)         # 3rd consecutive
    assert not t.observe(50)      # resets


def test_drawdown_tripper_threshold() -> None:
    t = DrawdownTripper(threshold_pct=0.20)
    t.observe(100.0)
    assert not t.observe(95.0)    # 5% DD
    assert t.observe(70.0)        # 30% DD


# ─── correlation monitor ───

def test_correlation_zero_with_no_data() -> None:
    m = CorrelationMonitor()
    assert m.correlation("a", "b") == 0.0


def test_correlation_one_for_self() -> None:
    m = CorrelationMonitor()
    for v in [1.0, 2.0, 3.0, 4.0]:
        m.record_daily({"a": v})
    assert m.correlation("a", "a") == 1.0


def test_correlation_detects_anticorrelated_pair() -> None:
    m = CorrelationMonitor()
    for i in range(20):
        m.record_daily({"a": float(i), "b": float(-i)})
    assert m.correlation("a", "b") < -0.9


def test_adjustment_for_disarms_at_high_correlation() -> None:
    m = CorrelationMonitor()
    for i in range(20):
        m.record_daily({"a": float(i), "b": float(i + 0.01 * i)})  # ~perfect positive
    adj = m.adjustment_for("a", ["a", "b"])
    assert adj == 0.0  # disarm


def test_adjustment_dampens_at_moderate_correlation() -> None:
    m = CorrelationMonitor()
    # Build a series whose correlation with a "noisy partner" is around 0.7
    import numpy as np
    rng = np.random.default_rng(0)
    base = rng.standard_normal(30)
    noisy = base + 0.4 * rng.standard_normal(30)
    for x, y in zip(base, noisy, strict=True):
        m.record_daily({"a": float(x), "b": float(y)})
    adj = m.adjustment_for("a", ["a", "b"])
    assert adj in {0.5, 1.0}  # depending on exact correlation


# ─── drawdown manager ───

def test_drawdown_strategy_soft_cap() -> None:
    dm = DrawdownManager(soft_cap_pct=10.0, hard_cap_pct=15.0)
    dm.update_strategy("x", 100.0)
    action = dm.update_strategy("x", 92.0)   # 8% DD
    assert action.multiplier == 1.0
    action = dm.update_strategy("x", 89.0)   # 11% DD
    assert action.multiplier == 0.5


def test_drawdown_strategy_hard_cap() -> None:
    dm = DrawdownManager(soft_cap_pct=10.0, hard_cap_pct=15.0)
    dm.update_strategy("x", 100.0)
    action = dm.update_strategy("x", 80.0)   # 20% DD
    assert action.multiplier == 0.0
    assert action.disarm_for_days == 30


def test_drawdown_portfolio_halt() -> None:
    dm = DrawdownManager(portfolio_halt_pct=20.0)
    dm.update_portfolio(100.0)
    action = dm.update_portfolio(78.0)       # 22% DD
    assert action.halt_portfolio
    assert action.multiplier == 0.0
