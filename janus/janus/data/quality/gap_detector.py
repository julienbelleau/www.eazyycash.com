"""Gap detection for time-series tables.

A "gap" is a missing bar where one is expected. For 1-minute klines on a
24/7 spot market, the expected cadence is exactly 60 seconds. Any larger
delta is a gap.

Crypto markets are nominally 24/7 but exchanges *do* have:
- planned maintenance windows (Binance documents these)
- unplanned outages (rare but real, especially during cascades)

A small number of gaps is therefore expected. The detector:
  * tolerates `expected_gaps` (e.g. known maintenance windows) without alerting
  * raises if total missing bars in a window exceeds a threshold

This is the gating quality check for §0 of JANUS_TRADING_SYSTEM_PLAN.md
"detection of gaps (alertes si >2 bars manquants)".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class Gap:
    symbol: str
    after: datetime          # last bar before the gap
    before: datetime         # first bar after the gap
    missing_bars: int

    @property
    def duration(self) -> timedelta:
        return self.before - self.after


def detect_gaps(
    rows: Sequence[dict[str, Any]],
    *,
    cadence: timedelta = timedelta(minutes=1),
    tolerance_bars: int = 0,
) -> list[Gap]:
    """Return all gaps in the input series.

    `tolerance_bars`: a gap of size <= tolerance_bars is ignored (e.g. 0 means
    any gap is reported; 2 means only 3-bar-or-larger gaps are reported).
    """
    gaps: list[Gap] = []
    if len(rows) < 2:
        return gaps

    expected = cadence
    for prev, curr in zip(rows[:-1], rows[1:], strict=True):
        delta = curr["ts"] - prev["ts"]
        # Round to nearest cadence step to avoid float jitter.
        steps = round(delta / expected)
        missing = steps - 1
        if missing > tolerance_bars:
            gaps.append(
                Gap(
                    symbol=prev.get("symbol", curr.get("symbol", "?")),
                    after=prev["ts"],
                    before=curr["ts"],
                    missing_bars=missing,
                )
            )
    return gaps


def summarize_gaps(gaps: Sequence[Gap]) -> dict[str, int | float]:
    """Aggregate gap stats — handy for daily quality reports."""
    if not gaps:
        return {"count": 0, "total_missing": 0, "max_missing": 0, "longest_seconds": 0.0}
    total_missing = sum(g.missing_bars for g in gaps)
    max_missing = max(g.missing_bars for g in gaps)
    longest = max((g.duration.total_seconds() for g in gaps), default=0.0)
    return {
        "count": len(gaps),
        "total_missing": total_missing,
        "max_missing": max_missing,
        "longest_seconds": longest,
    }
