"""Cross-source price validator tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from janus.data.quality.cross_source import cross_source_divergences


def _row(ts: datetime, close: float) -> dict[str, object]:
    return {"symbol": "BTCUSDT", "ts": ts, "close": Decimal(str(close))}


def test_aligned_series_no_divergence() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    a = [_row(base + timedelta(minutes=i), 40_000 + i) for i in range(10)]
    b = [_row(base + timedelta(minutes=i), 40_000 + i) for i in range(10)]
    assert cross_source_divergences(a, b) == []


def test_persistent_divergence_flagged() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    a = [_row(base + timedelta(minutes=i), 40_000) for i in range(5)]
    # Source B is consistently 100 bps off => 1% deviation.
    b = [_row(base + timedelta(minutes=i), 40_400) for i in range(5)]
    div = cross_source_divergences(a, b, threshold_bps=25.0)
    assert len(div) == 5
    assert all(d.bps > 25 for d in div)


def test_disjoint_timestamps_ignored() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    a = [_row(base + timedelta(minutes=i), 40_000) for i in range(5)]
    b = [_row(base + timedelta(minutes=i + 100), 30_000) for i in range(5)]
    # No timestamp overlap → no divergences detected (gap detector's job).
    assert cross_source_divergences(a, b) == []


def test_max_report_truncates() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    a = [_row(base + timedelta(minutes=i), 40_000) for i in range(20)]
    b = [_row(base + timedelta(minutes=i), 50_000) for i in range(20)]
    div = cross_source_divergences(a, b, threshold_bps=10.0, max_report=5)
    assert len(div) == 5
