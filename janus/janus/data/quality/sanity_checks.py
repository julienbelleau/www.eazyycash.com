"""OHLC sanity checks.

These are the *invariants* that must hold for any valid bar regardless of
exchange or asset. The DB enforces a subset via CHECK constraints, but we
also validate at the loader layer so we can reject batches with a meaningful
error before they ever touch the DB (faster feedback during backfill).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from janus.errors import DataQualityViolation


def check_ohlc_row(row: dict[str, Any]) -> None:
    """Raise DataQualityViolation if a single row violates OHLC invariants."""
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    v = row["volume"]
    n = row["trade_count"]

    if h < l:
        raise DataQualityViolation("ohlc.high_lt_low", f"{row.get('symbol')}@{row.get('ts')}")
    if h < o or h < c:
        raise DataQualityViolation("ohlc.high_lt_oc", f"{row.get('symbol')}@{row.get('ts')}")
    if l > o or l > c:
        raise DataQualityViolation("ohlc.low_gt_oc", f"{row.get('symbol')}@{row.get('ts')}")
    if v < 0:
        raise DataQualityViolation("ohlc.volume_negative", f"{row.get('symbol')}@{row.get('ts')}")
    if n < 0:
        raise DataQualityViolation("ohlc.trade_count_negative", f"{row.get('symbol')}@{row.get('ts')}")
    # Detect nonsensical volume = 0 with trade_count > 0 (or vice versa).
    if (v == 0 and n > 0) or (v > 0 and n == 0):
        raise DataQualityViolation(
            "ohlc.volume_trades_inconsistent",
            f"{row.get('symbol')}@{row.get('ts')} v={v} n={n}",
        )


def check_ohlc_batch(rows: Iterable[dict[str, Any]]) -> int:
    """Run sanity on every row; return count. Raise on first violation."""
    count = 0
    for r in rows:
        check_ohlc_row(r)
        count += 1
    return count


def check_monotonic_timestamps(rows: Sequence[dict[str, Any]]) -> None:
    """Rows must be strictly increasing by ts.

    A non-monotonic batch usually indicates a pagination bug (cursor moved
    backwards) — surface it loudly rather than letting the on-conflict
    insert silently dedup.
    """
    if not rows:
        return
    last = rows[0]["ts"]
    for r in rows[1:]:
        if r["ts"] <= last:
            raise DataQualityViolation(
                "ohlc.timestamps_non_monotonic",
                f"prev={last}, curr={r['ts']}",
            )
        last = r["ts"]


def estimate_typical_price(row: dict[str, Any]) -> Decimal:
    """OHLC typical price (HLC/3) — used by some sanity heuristics."""
    return (Decimal(row["high"]) + Decimal(row["low"]) + Decimal(row["close"])) / Decimal(3)
