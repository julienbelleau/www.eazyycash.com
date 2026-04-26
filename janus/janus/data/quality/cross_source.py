"""Cross-source price validation (UPGRADES §0.6).

When the same symbol is ingested from two exchanges (e.g. Binance + Bybit),
the close-to-close price difference at the same timestamp should be small —
the spread is essentially the basis between identical instruments.

Persistent divergence > N basis points is one of the strongest signals that
*one of the feeds is broken*. We've seen this in the wild: Binance
2022-10-10 mid-stamp drift, Bybit funding API caching issue 2023-Q3.

The validator returns a structured report; the caller (typically a daily
quality job) decides whether to alert / kill-switch.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Divergence:
    symbol: str
    ts: datetime
    price_a: Decimal
    price_b: Decimal
    bps: float        # absolute basis points: |a-b| / mid * 10_000

    @property
    def is_significant(self) -> bool:
        # Default heuristic; callers override via threshold_bps in the validator.
        return self.bps > 25  # 0.25%


def _index_by_ts(rows: Sequence[dict[str, Any]]) -> dict[datetime, dict[str, Any]]:
    return {r["ts"]: r for r in rows}


def cross_source_divergences(
    rows_a: Sequence[dict[str, Any]],
    rows_b: Sequence[dict[str, Any]],
    *,
    threshold_bps: float = 25.0,
    max_report: int = 100,
) -> list[Divergence]:
    """Compare close prices at matching timestamps; return divergences over threshold.

    Inputs must be OHLCV row dicts (or anything carrying `ts`, `symbol`, `close`).
    Series are inner-joined on `ts`; bars present in only one source are ignored
    (gap detection is the right tool for that).
    """
    a = _index_by_ts(rows_a)
    b = _index_by_ts(rows_b)

    common_ts = sorted(set(a) & set(b))
    out: list[Divergence] = []
    for ts in common_ts:
        ra = a[ts]
        rb = b[ts]
        pa = Decimal(ra["close"])
        pb = Decimal(rb["close"])
        mid = (pa + pb) / Decimal(2)
        if mid == 0:
            continue
        bps = float(abs(pa - pb) / mid * Decimal(10_000))
        if bps > threshold_bps:
            out.append(Divergence(symbol=ra.get("symbol", "?"), ts=ts, price_a=pa, price_b=pb, bps=bps))
            if len(out) >= max_report:
                break
    return out
