"""Position sizing — Kelly + vol overlay + caps."""

from __future__ import annotations

from decimal import Decimal

import pytest

from janus.risk.position_sizing import (
    SizingPolicy,
    StrategyEdge,
    kelly_fraction,
    position_size_quote,
    vol_overlay_multiplier,
)


def test_kelly_zero_with_no_edge() -> None:
    edge = StrategyEdge(win_rate=0.5, avg_win_pct=0.01, avg_loss_pct=0.01)
    # 50/50 with equal win/loss → Kelly = 0
    assert kelly_fraction(edge) == 0.0


def test_kelly_positive_with_real_edge() -> None:
    edge = StrategyEdge(win_rate=0.6, avg_win_pct=0.02, avg_loss_pct=0.01)
    # Kelly = 0.6 - 0.4/(2.0) = 0.6 - 0.2 = 0.4
    assert abs(kelly_fraction(edge) - 0.4) < 1e-9


def test_kelly_zero_with_negative_inputs() -> None:
    assert kelly_fraction(StrategyEdge(0.6, 0.0, 0.01)) == 0.0
    assert kelly_fraction(StrategyEdge(0.6, 0.02, 0.0)) == 0.0
    assert kelly_fraction(StrategyEdge(0.0, 0.02, 0.01)) == 0.0
    assert kelly_fraction(StrategyEdge(1.0, 0.02, 0.01)) == 0.0


def test_vol_overlay_capped_above() -> None:
    # Realised σ near zero → overlay would be huge but capped at max_multiplier.
    m = vol_overlay_multiplier(0.001, 0.15, max_multiplier=2.0)
    assert m == 2.0


def test_vol_overlay_scales_down_in_high_vol() -> None:
    # Realised σ = 0.30, target = 0.15 → overlay = 0.5
    m = vol_overlay_multiplier(0.30, 0.15)
    assert abs(m - 0.5) < 1e-9


def test_position_size_respects_per_trade_cap() -> None:
    edge = StrategyEdge(win_rate=0.7, avg_win_pct=0.05, avg_loss_pct=0.01)
    # Strong edge — Kelly is huge; per-trade cap (10%) should clip it.
    size = position_size_quote(
        portfolio_quote=Decimal("100000"),
        edge=edge,
        realised_sigma_annual=0.10,
        policy=SizingPolicy(per_trade_cap_pct=10.0),
    )
    assert size == Decimal("10000")  # 10% of 100k


def test_position_size_respects_per_strategy_cap() -> None:
    edge = StrategyEdge(win_rate=0.7, avg_win_pct=0.05, avg_loss_pct=0.01)
    size = position_size_quote(
        portfolio_quote=Decimal("100000"),
        edge=edge,
        realised_sigma_annual=0.10,
        policy=SizingPolicy(per_trade_cap_pct=10.0, per_strategy_cap_pct=25.0),
        current_strategy_exposure_pct=20.0,    # only 5% headroom left
    )
    assert size == Decimal("5000")


def test_zero_size_when_no_edge() -> None:
    size = position_size_quote(
        portfolio_quote=Decimal("100000"),
        edge=StrategyEdge(0.5, 0.01, 0.01),    # no edge
        realised_sigma_annual=0.10,
    )
    assert size == Decimal(0)


def test_zero_size_when_strategy_cap_exhausted() -> None:
    edge = StrategyEdge(0.7, 0.05, 0.01)
    size = position_size_quote(
        portfolio_quote=Decimal("100000"),
        edge=edge,
        realised_sigma_annual=0.10,
        current_strategy_exposure_pct=25.0,   # at cap
    )
    assert size == Decimal(0)


@pytest.mark.parametrize("portfolio,expected_max", [
    (Decimal("10000"), Decimal("1000")),
    (Decimal("250000"), Decimal("25000")),
])
def test_per_trade_cap_scales_with_portfolio(portfolio: Decimal, expected_max: Decimal) -> None:
    edge = StrategyEdge(0.7, 0.05, 0.01)
    size = position_size_quote(
        portfolio_quote=portfolio,
        edge=edge,
        realised_sigma_annual=0.10,
    )
    assert size <= expected_max
