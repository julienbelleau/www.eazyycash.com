"""Pytest fixtures shared across all test packages.

Keep tests deterministic: a fixed seed is set on every test, and the
`pytest-randomly` plugin's seed is logged so flakes are reproducible.
"""

from __future__ import annotations

import os
import random
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pytest

# Ensure no stray .env from the host leaks into tests.
os.environ.setdefault("JANUS_ENV", "dev")
os.environ.setdefault("JANUS_LOG_JSON", "false")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("JANUS_RANDOM_SEED", "42")


@pytest.fixture(autouse=True)
def _fix_seeds() -> Iterator[None]:
    """Per-test seed reset; bullet-proof determinism."""
    random.seed(42)
    np.random.seed(42)
    yield


@pytest.fixture()
def base_ts() -> datetime:
    return datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def make_bar() -> "BarFactory":
    """Factory producing valid OHLCV bar dicts."""

    def _make(
        ts: datetime,
        symbol: str = "BTCUSDT",
        price: float = 40_000.0,
        spread: float = 50.0,
        volume: float = 12.5,
    ) -> dict[str, object]:
        o = Decimal(str(price))
        h = o + Decimal(str(spread))
        l = o - Decimal(str(spread))
        c = o + Decimal(str(spread / 2))
        return {
            "symbol": symbol,
            "ts": ts,
            "open": o, "high": h, "low": l, "close": c,
            "volume": Decimal(str(volume)),
            "quote_volume": Decimal(str(volume * price)),
            "trade_count": 100,
            "taker_buy_volume": Decimal(str(volume / 2)),
            "taker_buy_quote_volume": Decimal(str((volume / 2) * price)),
        }

    return _make


# Type-only alias for IDE hints.
class BarFactory:  # pragma: no cover
    def __call__(
        self,
        ts: datetime,
        symbol: str = "BTCUSDT",
        price: float = 40_000.0,
        spread: float = 50.0,
        volume: float = 12.5,
    ) -> dict[str, object]: ...


@pytest.fixture()
def contiguous_bars(make_bar: BarFactory, base_ts: datetime) -> list[dict[str, object]]:
    """120 minutes of contiguous valid bars."""
    return [make_bar(base_ts + timedelta(minutes=i)) for i in range(120)]
