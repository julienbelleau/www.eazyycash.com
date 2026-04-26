"""Gap detector — both example-based and property-based tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from janus.data.quality.gap_detector import detect_gaps, summarize_gaps


def _row(ts: datetime) -> dict[str, object]:
    return {"symbol": "BTCUSDT", "ts": ts, "close": 1}


def test_no_gaps_in_contiguous_series() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [_row(base + timedelta(minutes=i)) for i in range(60)]
    assert detect_gaps(rows) == []


def test_single_one_bar_gap_detected() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [_row(base + timedelta(minutes=i)) for i in (0, 1, 2, 4, 5)]  # missing minute 3
    gaps = detect_gaps(rows)
    assert len(gaps) == 1
    assert gaps[0].missing_bars == 1
    assert gaps[0].duration == timedelta(minutes=2)


def test_tolerance_suppresses_small_gaps() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [_row(base + timedelta(minutes=i)) for i in (0, 1, 3, 5)]
    assert detect_gaps(rows, tolerance_bars=1) == []
    assert len(detect_gaps(rows, tolerance_bars=0)) == 2


def test_summarize_empty() -> None:
    s = summarize_gaps([])
    assert s == {"count": 0, "total_missing": 0, "max_missing": 0, "longest_seconds": 0.0}


# ─── property: detector finds exactly the bars we removed ───
@given(
    drops=st.sets(st.integers(min_value=1, max_value=58), min_size=1, max_size=10),
)
@settings(max_examples=100)
def test_detect_recovers_removed_bars(drops: set[int]) -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    keep_indices = sorted(set(range(60)) - drops)
    rows = [_row(base + timedelta(minutes=i)) for i in keep_indices]
    gaps = detect_gaps(rows)
    total_missing = sum(g.missing_bars for g in gaps)
    assert total_missing == len(drops)
