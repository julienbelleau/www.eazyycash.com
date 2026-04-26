"""Tests for Binance loader parse() functions.

Parsing is the surface where exchange shape changes break us. We freeze
example payloads (recorded from real responses) and assert the parsed shape
matches the DB schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from janus.data.loaders.binance import (
    BinanceAggTradesLoader,
    BinanceFundingLoader,
    BinanceKlineLoader,
    BinanceOpenInterestLoader,
)
from janus.errors import PermanentError


# ─── klines ───

KLINE_RAW: list[list[object]] = [
    [
        1704067200000, "42000.0", "42100.0", "41900.0", "42050.0",
        "100.5", 1704067259999, "4225025.0", 850, "60.0", "2523000.0", "0",
    ],
    [
        1704067260000, "42050.0", "42150.0", "42000.0", "42120.0",
        "98.0", 1704067319999, "4127760.0", 800, "55.0", "2312000.0", "0",
    ],
]


def test_kline_parser_shape_and_types() -> None:
    loader = BinanceKlineLoader()
    rows = loader.parse(KLINE_RAW, symbol="BTCUSDT")
    assert len(rows) == 2

    r = rows[0]
    assert r["symbol"] == "BTCUSDT"
    assert r["ts"] == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert r["open"] == Decimal("42000.0")
    assert r["high"] == Decimal("42100.0")
    assert r["low"] == Decimal("41900.0")
    assert r["close"] == Decimal("42050.0")
    assert r["volume"] == Decimal("100.5")
    assert r["trade_count"] == 850


def test_kline_parser_drops_incomplete_bar() -> None:
    incomplete = list(KLINE_RAW[0])
    # Set close_time so close_time - open_time != 59999 (incomplete bar)
    incomplete[6] = incomplete[0] + 30_000  # only 30s elapsed
    loader = BinanceKlineLoader()
    rows = loader.parse([incomplete], symbol="BTCUSDT")
    assert rows == []


def test_kline_parser_requires_symbol() -> None:
    loader = BinanceKlineLoader()
    with pytest.raises(PermanentError, match="symbol required"):
        loader.parse(KLINE_RAW)


# ─── funding ───

FUNDING_RAW: list[dict[str, object]] = [
    {"symbol": "BTCUSDT", "fundingTime": 1704067200000, "fundingRate": "0.0001", "markPrice": "42050.0"},
    {"symbol": "BTCUSDT", "fundingTime": 1704096000000, "fundingRate": "-0.00005"},
]


def test_funding_parser_handles_optional_mark() -> None:
    loader = BinanceFundingLoader()
    rows = loader.parse(FUNDING_RAW)
    assert rows[0]["mark_price"] == Decimal("42050.0")
    assert rows[1]["mark_price"] is None
    assert rows[1]["rate"] == Decimal("-0.00005")


# ─── open interest ───

OI_RAW: list[dict[str, object]] = [
    {
        "symbol": "BTCUSDT",
        "sumOpenInterest": "12345.678",
        "sumOpenInterestValue": "519152400.0",
        "timestamp": 1704067200000,
    }
]


def test_open_interest_parser() -> None:
    loader = BinanceOpenInterestLoader()
    rows = loader.parse(OI_RAW)
    assert rows[0]["oi_contracts"] == Decimal("12345.678")
    assert rows[0]["oi_quote"] == Decimal("519152400.0")


# ─── agg trades ───

AGG_RAW: list[dict[str, object]] = [
    {"a": 1234567, "p": "42050.0", "q": "0.5", "T": 1704067200500, "m": True},
]


def test_agg_trades_parser() -> None:
    loader = BinanceAggTradesLoader()
    rows = loader.parse(AGG_RAW, symbol="BTCUSDT")
    assert rows[0]["trade_id"] == 1234567
    assert rows[0]["price"] == Decimal("42050.0")
    assert rows[0]["is_buyer_maker"] is True
