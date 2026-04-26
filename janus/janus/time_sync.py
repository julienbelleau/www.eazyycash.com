"""Clock synchronization check.

Point-in-time correctness — the cornerstone invariant of Janus — requires
that the local clock be aligned with exchange time within a known tolerance.
A 30-second drift on a 1-minute bar means features can be assigned to the
wrong bucket on resampling, producing silent look-ahead bias.

This module:
  * pings the Binance server-time endpoint (no auth required, latency ~50ms)
  * compares against the local UTC clock
  * raises `ClockDriftError` if drift exceeds settings.max_clock_drift_seconds

Call `assert_clock_in_sync()` once at process startup — *before* any ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from janus.config.settings import Settings, get_settings
from janus.errors import ClockDriftError, ExchangeUnavailableError

_BINANCE_TIME_URL = "https://api.binance.com/api/v3/time"


@dataclass(frozen=True)
class ClockReport:
    drift_seconds: float
    local_time: datetime
    server_time: datetime
    one_way_latency_ms: float


@retry(
    retry=retry_if_exception_type(ExchangeUnavailableError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
async def measure_clock_drift(client: httpx.AsyncClient | None = None) -> ClockReport:
    """Measure drift between local UTC and Binance server time.

    Uses the NTP-style midpoint estimate: `(t_send + t_recv) / 2` as the local
    timestamp at the moment the server stamped its time. Eliminates one-way
    latency from the drift estimate to first order.
    """
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))
    try:
        t_send = datetime.now(timezone.utc)
        try:
            response = await client.get(_BINANCE_TIME_URL)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            raise ExchangeUnavailableError(f"Binance time endpoint unreachable: {exc}") from exc
        t_recv = datetime.now(timezone.utc)

        server_ms: int = response.json()["serverTime"]
        server_time = datetime.fromtimestamp(server_ms / 1000.0, tz=timezone.utc)

        midpoint = t_send + (t_recv - t_send) / 2
        drift = (server_time - midpoint).total_seconds()
        latency_ms = (t_recv - t_send).total_seconds() * 1000.0

        return ClockReport(
            drift_seconds=drift,
            local_time=midpoint,
            server_time=server_time,
            one_way_latency_ms=latency_ms / 2.0,
        )
    finally:
        if own_client:
            await client.aclose()


async def assert_clock_in_sync(settings: Settings | None = None) -> ClockReport:
    """Refuse to proceed if local clock drifts beyond tolerance.

    Raises `ClockDriftError` on violation. Logs the report on success.
    """
    settings = settings or get_settings()
    report = await measure_clock_drift()

    log = logger.bind(
        drift_s=report.drift_seconds,
        latency_ms=report.one_way_latency_ms,
        tolerance_s=settings.max_clock_drift_seconds,
    )

    if abs(report.drift_seconds) > settings.max_clock_drift_seconds:
        log.error("clock drift exceeds tolerance — refusing to start")
        raise ClockDriftError(
            f"clock drift {report.drift_seconds:+.3f}s exceeds tolerance "
            f"{settings.max_clock_drift_seconds}s — sync NTP/chrony before retrying"
        )

    log.info("clock in sync")
    return report
