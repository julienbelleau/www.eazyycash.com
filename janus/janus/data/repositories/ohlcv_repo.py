"""OHLCV repository — the only public interface to OHLCV data.

Strategies and feature engines never query the DB directly. They go through
this repo, which:
  * accepts a `(symbol, start, end, resolution)` tuple
  * routes to the right TimescaleDB hypertable / continuous aggregate
  * enforces point-in-time correctness: it is *impossible* to ask for data
    past the `as_of` argument — a backtest at t0 cannot leak future bars.

Resolutions higher than 1m read from the continuous aggregates created in
the initial migration (5m / 15m / 1h / 4h / 1d). The `1m` resolution reads
the base hypertable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Resolution = Literal["1m", "5m", "15m", "1h", "4h", "1d"]

_RES_TO_TABLE: Mapping[Resolution, str] = {
    "1m": "ohlcv_1m",
    "5m": "ohlcv_5m",
    "15m": "ohlcv_15m",
    "1h": "ohlcv_1h",
    "4h": "ohlcv_4h",
    "1d": "ohlcv_1d",
}

# The continuous aggregates use `bucket` as the time column; the base table uses `ts`.
_RES_TO_TS_COL: Mapping[Resolution, str] = {
    "1m": "ts",
    "5m": "bucket",
    "15m": "bucket",
    "1h": "bucket",
    "4h": "bucket",
    "1d": "bucket",
}


@dataclass(frozen=True)
class OhlcvBar:
    symbol: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class OhlcvRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
        resolution: Resolution = "1m",
        source: str = "binance",
        as_of: datetime | None = None,
    ) -> pl.DataFrame:
        """Return bars in `[start, end]`, capped to `as_of` if provided.

        `as_of` is the point-in-time correctness fence: if the caller is
        running a backtest at simulated time T, they must pass `as_of=T`.
        Bars with ts > as_of are filtered out at the SQL layer.
        """
        if start > end:
            raise ValueError(f"start ({start}) must be <= end ({end})")
        if as_of is not None and as_of < end:
            end = as_of

        table = _RES_TO_TABLE[resolution]
        ts_col = _RES_TO_TS_COL[resolution]

        sql = text(
            f"""
            SELECT
                symbol,
                {ts_col} AS ts,
                open, high, low, close, volume
            FROM {table}
            WHERE symbol = :symbol
              AND source = :source
              AND {ts_col} >= :start
              AND {ts_col} <= :end
            ORDER BY {ts_col} ASC
            """
        )
        result = await self._session.execute(
            sql, {"symbol": symbol, "source": source, "start": start, "end": end}
        )
        rows = [dict(r._mapping) for r in result]
        if not rows:
            return pl.DataFrame(
                schema={
                    "symbol": pl.Utf8, "ts": pl.Datetime("us", "UTC"),
                    "open": pl.Float64, "high": pl.Float64, "low": pl.Float64,
                    "close": pl.Float64, "volume": pl.Float64,
                }
            )
        return pl.DataFrame(rows)

    async def latest_ts(self, *, symbol: str, source: str = "binance") -> datetime | None:
        """Used by backfill to know where to resume."""
        sql = text("SELECT MAX(ts) AS ts FROM ohlcv_1m WHERE symbol = :s AND source = :src")
        result = await self._session.execute(sql, {"s": symbol, "src": source})
        row = result.first()
        return row.ts if row and row.ts else None
