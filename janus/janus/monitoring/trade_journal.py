"""Trade journal — append-only JSONL record of every fill.

The journal is the *audit log* for the system. Every trade in production
must be inspectable with a `cat | jq` after the fact:
  - what signal triggered it?
  - what feature values were captured at decision time?
  - what was the slippage?
  - which exit reason fired (TP, SL, time stop, etc.)?

The journal is also the input to the daily report (`scripts/daily_report.py`)
which posts a Telegram digest each UTC midnight.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class JournalEntry:
    ts: datetime
    strategy_id: str
    symbol: str
    intent: str
    side: str
    qty: Decimal
    fill_price: Decimal
    slippage_bps: float
    signal_name: str | None
    signal_features: Mapping[str, float] | None
    client_order_id: UUID
    notes: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "ts": self.ts.isoformat(),
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "intent": self.intent,
            "side": self.side,
            "qty": str(self.qty),
            "fill_price": str(self.fill_price),
            "slippage_bps": self.slippage_bps,
            "signal_name": self.signal_name,
            "signal_features": dict(self.signal_features) if self.signal_features else None,
            "client_order_id": str(self.client_order_id),
            "notes": self.notes,
        }


class TradeJournal:
    """Async-friendly JSONL writer. Locks per-process for safety."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def append(self, entry: JournalEntry) -> None:
        path = self.root / f"{entry.strategy_id}-{entry.ts:%Y-%m}.jsonl"
        line = json.dumps(entry.to_jsonable())
        async with self._lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def read_day(self, date_utc: datetime, strategy_id: str | None = None) -> list[dict[str, Any]]:
        """Synchronously read all entries for `date_utc` (the UTC date portion).

        Used by the daily report. We don't load the entire history — just
        the requested day's slice from the per-month files.
        """
        target = date_utc.date()
        out: list[dict[str, Any]] = []
        pattern = f"*-{target:%Y-%m}.jsonl"
        for path in sorted(self.root.glob(pattern)):
            if strategy_id and not path.name.startswith(f"{strategy_id}-"):
                continue
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = datetime.fromisoformat(record["ts"])
                    if ts.date() == target:
                        out.append(record)
        return out
