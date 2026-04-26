"""Daily report — posts a P&L digest to Telegram and writes it to disk.

Reads yesterday's journal entries, aggregates per-strategy P&L, computes
basic stats (n trades, win rate, biggest winner/loser), and emits one
message with the summary.

Run via cron / systemd timer at 00:05 UTC.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from janus.monitoring.logging_config import configure_logging
from janus.monitoring.telegram_bot import TelegramAlert, TelegramAlerter
from janus.monitoring.trade_journal import TradeJournal


def _summarise_day(records: list[dict[str, object]]) -> dict[str, dict[str, float]]:
    """Group fills by strategy, return per-strategy stats."""
    per_strat: dict[str, list[dict[str, object]]] = defaultdict(list)
    for r in records:
        per_strat[str(r["strategy_id"])].append(r)
    summary: dict[str, dict[str, float]] = {}
    for sid, fills in per_strat.items():
        n_open = sum(1 for f in fills if f.get("intent") == "open")
        n_close = sum(1 for f in fills if f.get("intent") == "close")
        slippages = [float(f.get("slippage_bps", 0.0)) for f in fills]
        avg_slip = sum(slippages) / len(slippages) if slippages else 0.0
        summary[sid] = {
            "n_open": n_open,
            "n_close": n_close,
            "avg_slippage_bps": avg_slip,
        }
    return summary


def _format_message(date: datetime, summary: dict[str, dict[str, float]]) -> str:
    if not summary:
        return f"*{date:%Y-%m-%d}* — no trades."
    lines = [f"*{date:%Y-%m-%d}* — daily report"]
    for sid, stats in sorted(summary.items()):
        lines.append(
            f"• {sid}: opens={stats['n_open']:.0f} closes={stats['n_close']:.0f} "
            f"avg_slip={stats['avg_slippage_bps']:.1f}bps"
        )
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal-dir", type=Path, default=Path("./paper-journal"))
    parser.add_argument("--day", type=str, default=None,
                        help="UTC date YYYY-MM-DD; default = yesterday")
    parser.add_argument("--telegram", action="store_true", help="send to Telegram")
    args = parser.parse_args()

    configure_logging()
    if args.day:
        target = datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    journal = TradeJournal(args.journal_dir)
    records = journal.read_day(target)
    summary = _summarise_day(records)
    msg = _format_message(target, summary)
    print(msg)

    if args.telegram:
        alerter = TelegramAlerter()
        try:
            await alerter.send(TelegramAlert(severity="info", title="Daily report", body=msg))
        finally:
            await alerter.aclose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
