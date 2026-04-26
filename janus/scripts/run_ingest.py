"""Ingestion worker entrypoint.

Long-running process: connects to Binance via the websocket manager and
streams OHLCV / liquidations into the DB through the existing loaders.

Phase 0 ships the websocket supervisor + outbox; this entrypoint wires
them to the live publisher in subsequent commits. For now it asserts
clock sync, runs a periodic backfill catch-up, and idles — proves the
service starts cleanly on Railway.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from datetime import datetime, timedelta, timezone

from loguru import logger

from janus.config.settings import get_settings
from janus.monitoring.logging_config import configure_logging
from janus.monitoring.prometheus_metrics import start_metrics_server
from janus.time_sync import assert_clock_in_sync


_STOP = asyncio.Event()


def _install_signal_handlers() -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _STOP.set)


async def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    await assert_clock_in_sync(settings)
    start_metrics_server(settings.observability.prometheus_port)

    logger.info("janus-ingest started — waiting for live wiring (websocket → outbox publisher)")
    _install_signal_handlers()

    # Idle loop with periodic heartbeat so Railway sees the process is alive.
    while not _STOP.is_set():
        try:
            await asyncio.wait_for(_STOP.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.info("ingest heartbeat — alive @ {}", datetime.now(timezone.utc).isoformat())
    logger.info("janus-ingest shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
