"""Strategy primitives — confidence bounds, position math."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from janus.strategies.base import Position, Side, Signal


def test_signal_confidence_bounds() -> None:
    Signal(name="x", confidence=0.0, features={})  # boundary OK
    Signal(name="x", confidence=1.0, features={})  # boundary OK
    with pytest.raises(ValueError, match="confidence"):
        Signal(name="x", confidence=-0.01, features={})
    with pytest.raises(ValueError, match="confidence"):
        Signal(name="x", confidence=1.01, features={})


def test_position_unrealized_pnl_long() -> None:
    p = Position(
        symbol="BTCUSDT", side=Side.LONG, qty=Decimal("0.5"),
        avg_entry_price=Decimal("40000"),
        opened_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        strategy_id="x",
    )
    assert p.unrealized_pnl(Decimal("41000")) == Decimal("500")
    assert p.unrealized_pnl(Decimal("39000")) == Decimal("-500")


def test_position_unrealized_pnl_short() -> None:
    p = Position(
        symbol="BTCUSDT", side=Side.SHORT, qty=Decimal("0.5"),
        avg_entry_price=Decimal("40000"),
        opened_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        strategy_id="x",
    )
    assert p.unrealized_pnl(Decimal("41000")) == Decimal("-500")
    assert p.unrealized_pnl(Decimal("39000")) == Decimal("500")
