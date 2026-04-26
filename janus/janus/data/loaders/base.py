"""Loader scaffolding shared by every data source.

Responsibilities:
- Async rate limiting via aiolimiter (token bucket).
- Retry with exponential backoff via tenacity, narrowed to TransientError.
- Content-hash idempotency: each batch is hashed (sha256 of canonical JSON);
  re-running a backfill produces no duplicate rows because the loader skips
  batches whose hash already exists in `ingest_jobs`.
- Job lifecycle in `ingest_jobs`: pending → running → succeeded/failed.
- Bronze-layer audit: raw payload archived in `raw_payloads` (gzipped).

Subclasses implement `fetch()` and `parse()`. The base class drives the
concurrency, retry, dedup, and persistence.
"""

from __future__ import annotations

import abc
import gzip
import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from aiolimiter import AsyncLimiter
from loguru import logger
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from janus.data.schema.models import ingest_jobs, raw_payloads
from janus.errors import PermanentError, TransientError

T = TypeVar("T")  # parsed row type


def new_job_id() -> str:
    """ULID-like sortable opaque id (time-prefixed, 26 chars URL-safe)."""
    # We don't need ULID's full spec — sortable + unique + opaque is enough.
    millis = int(datetime.now(timezone.utc).timestamp() * 1000)
    rand = secrets.token_hex(8)  # 16 hex chars = 64 bits of randomness
    return f"{millis:013d}{rand}"  # 13 + 16 = 29 chars, fits VARCHAR(32)


def content_hash(payload: Any) -> str:
    """Deterministic sha256 over canonical JSON. Used for idempotency keys."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IngestBatch(Generic[T]):
    """A batch of rows ready to be written, plus the metadata for audit."""

    source: str
    dataset: str
    symbol: str | None
    range_start: datetime | None
    range_end: datetime | None
    rows: Sequence[T]
    raw_payload: Any
    content_hash: str


class BaseLoader(abc.ABC):
    """Base class for any data source.

    Subclasses set:
        source        – e.g. "binance"
        dataset       – e.g. "klines_1m"
        rate_limit    – (calls, per_seconds), shared across instances of the source

    Subclasses implement:
        fetch(...) -> raw payload (dict / list / bytes)
        parse(raw, ...) -> Sequence[row dicts]  (column-aligned with target table)
    """

    source: str
    dataset: str
    rate_limit: tuple[int, float] = (10, 1.0)  # default 10 req / s

    # One limiter per (source, dataset) — class-level so multiple instances share it.
    _limiters: dict[tuple[str, str], AsyncLimiter] = {}

    def __init__(self) -> None:
        key = (self.source, self.dataset)
        if key not in self._limiters:
            calls, per_s = self.rate_limit
            self._limiters[key] = AsyncLimiter(calls, per_s)
        self._limiter = self._limiters[key]

    @abc.abstractmethod
    async def fetch(self, **kwargs: Any) -> Any:
        """Return the raw payload from the upstream API.

        May raise TransientError (retried) or PermanentError (escalated).
        """

    @abc.abstractmethod
    def parse(self, raw: Any, **kwargs: Any) -> Sequence[dict[str, Any]]:
        """Translate raw payload to target-table-shaped row dicts."""

    async def _retrying(self, fn: Callable[[], Awaitable[Any]]) -> Any:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(TransientError),
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=0.5, max=30),
            reraise=True,
        ):
            with attempt:
                async with self._limiter:
                    return await fn()
        # Unreachable; tenacity always returns a value or raises.
        raise PermanentError("retry loop exited without result")  # pragma: no cover

    async def fetch_with_retry(self, **kwargs: Any) -> Any:
        return await self._retrying(lambda: self.fetch(**kwargs))

    async def build_batch(
        self,
        symbol: str | None,
        range_start: datetime | None,
        range_end: datetime | None,
        **fetch_kwargs: Any,
    ) -> IngestBatch[dict[str, Any]]:
        """Fetch + parse + hash. Does not write to DB."""
        raw = await self.fetch_with_retry(symbol=symbol, **fetch_kwargs)
        rows = self.parse(raw, symbol=symbol)
        return IngestBatch(
            source=self.source,
            dataset=self.dataset,
            symbol=symbol,
            range_start=range_start,
            range_end=range_end,
            rows=rows,
            raw_payload=raw,
            content_hash=content_hash(raw),
        )

    async def already_ingested(self, session: AsyncSession, hash_: str) -> bool:
        """True if any prior succeeded job had the same content hash."""
        stmt = select(ingest_jobs.c.id).where(
            ingest_jobs.c.source == self.source,
            ingest_jobs.c.dataset == self.dataset,
            ingest_jobs.c.content_hash == hash_,
            ingest_jobs.c.status == "succeeded",
        )
        result = await session.execute(stmt)
        return result.first() is not None

    async def record_job_start(
        self,
        session: AsyncSession,
        batch: IngestBatch[Any],
        attempt: int = 1,
    ) -> str:
        job_id = new_job_id()
        await session.execute(
            insert(ingest_jobs).values(
                id=job_id,
                source=batch.source,
                dataset=batch.dataset,
                symbol=batch.symbol,
                range_start=batch.range_start,
                range_end=batch.range_end,
                status="running",
                attempt=attempt,
                content_hash=batch.content_hash,
                started_at=datetime.now(timezone.utc),
            )
        )
        return job_id

    async def record_job_done(
        self,
        session: AsyncSession,
        job_id: str,
        rows_written: int,
    ) -> None:
        await session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.id == job_id)
            .values(
                status="succeeded",
                rows_written=rows_written,
                finished_at=datetime.now(timezone.utc),
            )
        )

    async def record_job_failed(
        self,
        session: AsyncSession,
        job_id: str,
        error: str,
    ) -> None:
        await session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.id == job_id)
            .values(
                status="failed",
                error=error[:4000],
                finished_at=datetime.now(timezone.utc),
            )
        )

    async def archive_raw(
        self,
        session: AsyncSession,
        job_id: str,
        batch: IngestBatch[Any],
    ) -> None:
        """Persist the gzipped raw payload for audit / replay."""
        canonical = json.dumps(batch.raw_payload, default=str).encode("utf-8")
        compressed = gzip.compress(canonical, compresslevel=6)
        await session.execute(
            insert(raw_payloads).values(
                ingest_job_id=job_id,
                source=batch.source,
                dataset=batch.dataset,
                retrieved_at=datetime.now(timezone.utc),
                content_hash=batch.content_hash,
                payload_gzip=compressed,
            )
        )

    async def write_batch(
        self,
        session: AsyncSession,
        batch: IngestBatch[dict[str, Any]],
        target_insert: Callable[[Sequence[dict[str, Any]]], Any],
    ) -> int:
        """Wrap the full lifecycle: dedup → start → archive → upsert → done.

        `target_insert` is a callable that returns the SQLAlchemy insert
        statement for the destination table — subclasses pass it in because
        each table has different on-conflict semantics.
        """
        log = logger.bind(source=self.source, dataset=self.dataset, symbol=batch.symbol)

        if await self.already_ingested(session, batch.content_hash):
            log.info("batch already ingested (content_hash match) — skipping")
            return 0

        job_id = await self.record_job_start(session, batch)
        log = log.bind(job_id=job_id)
        try:
            await self.archive_raw(session, job_id, batch)
            # Stamp every row with the job id for audit/foreign-key-like joins.
            stamped = [dict(r, ingest_job_id=job_id, source=self.source) for r in batch.rows]
            if stamped:
                await session.execute(target_insert(stamped))
            await self.record_job_done(session, job_id, rows_written=len(stamped))
            await session.commit()
            log.info("batch ingested", rows=len(stamped))
            return len(stamped)
        except Exception as exc:
            await session.rollback()
            # Best-effort marking: open a fresh tx since we just rolled back.
            async with session.begin():
                await self.record_job_failed(session, job_id, repr(exc))
            log.exception("batch failed: {}", exc)
            raise
