"""Paper-trading runner.

Subscribes to live OHLCV via the websocket manager and feeds an Engine
configured with the paper broker. Writes fills + daily summary to the
trade journal.

Usage:
    poetry run python scripts/run_paper.py --strategies refractory --symbols BTCUSDT
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from loguru import logger

from janus.config.settings import get_settings
from janus.monitoring.logging_config import configure_logging
from janus.monitoring.prometheus_metrics import start_metrics_server
from janus.paper.simulator import PaperBroker, PaperRunner
from janus.time_sync import assert_clock_in_sync


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", required=True,
                        choices=["refractory", "narrative", "stablecoin"])
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--journal-dir", type=Path, default=Path("./paper-journal"))
    parser.add_argument("--starting-quote", type=Decimal, default=Decimal("100000"))
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    await assert_clock_in_sync()
    start_metrics_server(settings.observability.prometheus_port)

    broker = PaperBroker(cash=args.starting_quote)
    runner = PaperRunner(broker=broker, journal_dir=args.journal_dir)

    logger.info(
        "paper runner started — strategies={} symbols={}",
        args.strategies, args.symbols,
    )
    logger.warning(
        "live websocket -> engine wiring is the next deliverable; "
        "this script currently boots the runner and exits.",
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
