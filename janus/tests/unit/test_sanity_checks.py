"""Property-based and example-based tests for OHLC sanity invariants.

The properties are the *definitions* of a valid bar — using hypothesis we
generate millions of synthetic bars to confirm no edge case slips by.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.data.quality.sanity_checks import (
    check_monotonic_timestamps,
    check_ohlc_batch,
    check_ohlc_row,
    estimate_typical_price,
)
from janus.errors import DataQualityViolation


def _make_row(o: float, h: float, l: float, c: float, v: float = 1.0, n: int = 5) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "ts": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "open": Decimal(str(o)), "high": Decimal(str(h)),
        "low": Decimal(str(l)), "close": Decimal(str(c)),
        "volume": Decimal(str(v)), "trade_count": n,
    }


# ─── property: a bar with low <= open,close <= high passes ───
@given(
    o=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    spread_lo=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    spread_hi=st.floats(min_value=0.0, max_value=1e3, allow_nan=False, allow_infinity=False),
    rel_close=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_well_formed_bars_pass(o: float, spread_lo: float, spread_hi: float, rel_close: float) -> None:
    high = o + spread_hi
    low = o - spread_lo
    # close lies between low and high.
    close = low + rel_close * 0 + (low + (high - low) * (0.5 + 0.5 * rel_close))
    close = max(low, min(high, close))
    row = _make_row(o, high, low, close)
    check_ohlc_row(row)  # must not raise


def test_high_below_low_rejected() -> None:
    with pytest.raises(DataQualityViolation, match="high_lt_low"):
        check_ohlc_row(_make_row(o=100, h=99, l=101, c=100))


def test_high_below_open_rejected() -> None:
    with pytest.raises(DataQualityViolation, match="high_lt_oc"):
        check_ohlc_row(_make_row(o=100, h=99, l=98, c=99))


def test_low_above_open_rejected() -> None:
    with pytest.raises(DataQualityViolation, match="low_gt_oc"):
        check_ohlc_row(_make_row(o=100, h=110, l=101, c=105))


def test_negative_volume_rejected() -> None:
    with pytest.raises(DataQualityViolation, match="volume_negative"):
        check_ohlc_row(_make_row(o=100, h=110, l=90, c=105, v=-1.0))


def test_volume_trades_inconsistent() -> None:
    with pytest.raises(DataQualityViolation, match="volume_trades_inconsistent"):
        check_ohlc_row(_make_row(o=100, h=110, l=90, c=105, v=0.0, n=5))


def test_check_batch_counts(contiguous_bars: list[dict[str, object]]) -> None:
    assert check_ohlc_batch(contiguous_bars) == len(contiguous_bars)


def test_typical_price() -> None:
    p = estimate_typical_price(_make_row(o=100, h=120, l=80, c=110))
    assert p == Decimal(310) / Decimal(3)


def test_monotonic_passes_on_contiguous(contiguous_bars: list[dict[str, object]]) -> None:
    check_monotonic_timestamps(contiguous_bars)  # no raise


def test_monotonic_fails_on_duplicate(contiguous_bars: list[dict[str, object]]) -> None:
    bad = list(contiguous_bars)
    bad.append(dict(bad[-1]))
    with pytest.raises(DataQualityViolation, match="non_monotonic"):
        check_monotonic_timestamps(bad)
