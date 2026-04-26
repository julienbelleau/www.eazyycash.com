"""Liquidation event parser — defensive on malformed payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from janus.data.live.liquidation_stream import parse_force_order_event


def test_parse_long_liquidation() -> None:
    event = {
        "e": "forceOrder",
        "E": 1704067200500,
        "o": {
            "s": "BTCUSDT",
            "S": "SELL",                 # long got liquidated → exchange SELLS to close
            "p": "42050.0",
            "q": "0.5",
            "T": 1704067200500,
            "c": "abc-123",
        },
    }
    row = parse_force_order_event(event)
    assert row is not None
    assert row["symbol"] == "BTCUSDT"
    assert row["side"] == "long"
    assert row["price"] == Decimal("42050.0")
    assert row["quantity"] == Decimal("0.5")
    assert row["notional_usd"] == Decimal("42050.0") * Decimal("0.5")
    assert row["ts"] == datetime(2024, 1, 1, 0, 0, 0, 500_000, tzinfo=timezone.utc)
    assert row["source_order_id"] == "abc-123"


def test_parse_short_liquidation() -> None:
    event = {
        "o": {
            "s": "ETHUSDT", "S": "BUY",
            "p": "2500.0", "q": "1.0",
            "T": 1704067200500,
        }
    }
    row = parse_force_order_event(event)
    assert row is not None
    assert row["side"] == "short"


def test_parse_malformed_returns_none() -> None:
    assert parse_force_order_event({}) is None
    assert parse_force_order_event({"o": {}}) is None
    assert parse_force_order_event({"o": {"s": "X", "S": "BUY", "p": "?"}}) is None
