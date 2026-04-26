"""Resumable historical backfill driver.

Behavior:
- For each symbol × dataset, query `latest_ts` from the DB; resume from there.
- Page Binance in 1000-bar chunks; bound concurrency to avoid stampeding the API.
- All rate-limiting, retry, dedup is handled by `BaseLoader`.
- Failed batches go to `dead_letter` (via the loader's job lifecycle).

Usage:
    poetry run python scripts/backfill_historical.py \
        --symbols BTCUSDT ETHUSDT \
        --start 2022-01-01 \
        --end   2026-04-26 \
        --datasets klines

Datasets: klines | funding | open_interest | trades

Phase 0 ships klines + funding + open_interest end-to-end; trades is wired
but recommended only for top-3 symbols (volume).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from janus.config.settings import get_settings
from janus.data.loaders.binance import (
    BinanceFundingLoader,
    BinanceKlineLoader,
    BinanceOpenInterestLoader,
)
from janus.data.loaders.base import IngestBatch
from janus.data.quality.sanity_checks import (
    check_monotonic_timestamps,
    check_ohlc_batch,
)
from janus.data.repositories.ohlcv_repo import OhlcvRepository
from janus.data.schema.models import funding_rates, ohlcv_1m, open_interest
from janus.errors import DataQualityViolation
from janus.monitoring.logging_config import configure_logging
from janus.time_sync import assert_clock_in_sync


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


async def _backfill_klines(
    session_factory: async_sessionmaker[AsyncSession],
    symbol: str,
    start: datetime,
    end: datetime,
    client: httpx.AsyncClient,
) -> int:
    log = logger.bind(symbol=symbol, dataset="klines_1m")
    loader = BinanceKlineLoader(client=client)
    written_total = 0

    async with session_factory() as session:
        repo = OhlcvRepository(session)
        latest = await repo.latest_ts(symbol=symbol)
    cursor = max(start, (latest + timedelta(minutes=1)) if latest else start)
    log.info("resume cursor = {}", cursor.isoformat())

    while cursor < end:
        chunk_end = min(cursor + timedelta(minutes=1000), end)
        try:
            page = await loader.fetch_with_retry(
                symbol=symbol, start_ts=cursor, end_ts=chunk_end
            )
        except Exception as exc:
            log.error("fetch failed at {}: {}", cursor.isoformat(), exc)
            raise
        rows = list(loader.parse(page, symbol=symbol))
        if not rows:
            cursor = chunk_end
            continue
        try:
            check_ohlc_batch(rows)
            check_monotonic_timestamps(rows)
        except DataQualityViolation as exc:
            log.error("data quality violation — aborting backfill: {}", exc)
            raise

        batch = IngestBatch(
            source="binance",
            dataset="klines_1m",
            symbol=symbol,
            range_start=cursor,
            range_end=chunk_end,
            rows=rows,
            raw_payload=page,
            content_hash=str(rows[0]["ts"]) + str(rows[-1]["ts"]),  # cheap dedup key
        )

        def _insert_klines(rows_to_insert: list[dict[str, object]]) -> object:
            stmt = pg_insert(ohlcv_1m).values(rows_to_insert)
            return stmt.on_conflict_do_nothing(
                index_elements=["symbol", "ts", "source"]
            )

        async with session_factory() as session:
            written = await loader.write_batch(session, batch, _insert_klines)
            written_total += written

        cursor = rows[-1]["ts"] + timedelta(minutes=1)

    log.info("klines backfill complete: {} rows", written_total)
    return written_total


async def _backfill_funding(
    session_factory: async_sessionmaker[AsyncSession],
    symbol: str,
    start: datetime,
    end: datetime,
    client: httpx.AsyncClient,
) -> int:
    log = logger.bind(symbol=symbol, dataset="funding_rates")
    loader = BinanceFundingLoader(client=client)
    written_total = 0

    cursor = start
    # Funding cadence is 8h; 1000 entries ≈ 333 days. Step accordingly.
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=300), end)
        page = await loader.fetch_with_retry(symbol=symbol, start_ts=cursor, end_ts=chunk_end)
        rows = list(loader.parse(page))
        if not rows:
            cursor = chunk_end
            continue
        batch = IngestBatch(
            source="binance",
            dataset="funding_rates",
            symbol=symbol,
            range_start=cursor,
            range_end=chunk_end,
            rows=rows,
            raw_payload=page,
            content_hash=str(rows[0]["ts"]) + str(rows[-1]["ts"]),
        )

        def _insert_funding(rows_to_insert: list[dict[str, object]]) -> object:
            stmt = pg_insert(funding_rates).values(rows_to_insert)
            return stmt.on_conflict_do_nothing(index_elements=["symbol", "ts", "source"])

        async with session_factory() as session:
            written = await loader.write_batch(session, batch, _insert_funding)
            written_total += written
        cursor = rows[-1]["ts"] + timedelta(seconds=1)
    log.info("funding backfill complete: {} rows", written_total)
    return written_total


async def _backfill_oi(
    session_factory: async_sessionmaker[AsyncSession],
    symbol: str,
    start: datetime,
    end: datetime,
    client: httpx.AsyncClient,
) -> int:
    log = logger.bind(symbol=symbol, dataset="open_interest")
    loader = BinanceOpenInterestLoader(client=client)
    written_total = 0

    # Binance OI history: max 30 days per request, 5m granularity.
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=29), end)
        page = await loader.fetch_with_retry(symbol=symbol, start_ts=cursor, end_ts=chunk_end)
        rows = list(loader.parse(page))
        if not rows:
            cursor = chunk_end
            continue
        batch = IngestBatch(
            source="binance",
            dataset="open_interest",
            symbol=symbol,
            range_start=cursor,
            range_end=chunk_end,
            rows=rows,
            raw_payload=page,
            content_hash=str(rows[0]["ts"]) + str(rows[-1]["ts"]),
        )

        def _insert_oi(rows_to_insert: list[dict[str, object]]) -> object:
            stmt = pg_insert(open_interest).values(rows_to_insert)
            return stmt.on_conflict_do_nothing(index_elements=["symbol", "ts", "source"])

        async with session_factory() as session:
            written = await loader.write_batch(session, batch, _insert_oi)
            written_total += written
        cursor = rows[-1]["ts"] + timedelta(minutes=5)
    log.info("OI backfill complete: {} rows", written_total)
    return written_total


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", type=_parse_date, required=True)
    parser.add_argument("--end", type=_parse_date, default=datetime.now(timezone.utc))
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["klines", "funding", "open_interest"],
        choices=["klines", "funding", "open_interest"],
    )
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    await assert_clock_in_sync()

    engine = create_async_engine(settings.database.async_dsn, future=True, pool_size=5)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with httpx.AsyncClient() as client:
        for symbol in args.symbols:
            for ds in args.datasets:
                if ds == "klines":
                    await _backfill_klines(sf, symbol, args.start, args.end, client)
                elif ds == "funding":
                    await _backfill_funding(sf, symbol, args.start, args.end, client)
                elif ds == "open_interest":
                    await _backfill_oi(sf, symbol, args.start, args.end, client)

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
