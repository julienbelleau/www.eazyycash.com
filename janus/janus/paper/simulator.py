"""Paper trading simulator.

The plan §11 explicitly prefers a custom layer over Binance testnet —
testnet liquidity is unrealistic. This module wraps the live websocket
manager and feeds the same strategy / engine plumbing as the backtest.

Components:
- A `PaperOrderBook` that "fills" submitted orders against the simulator's
  view of the book (last orderbook snapshot if available, else trades).
- A `PaperBroker` exposing the same `submit/cancel/positions` surface a
  live broker will provide in Phase 1+ — strategies don't notice the swap.
- A `PaperRunner` driving the loop: subscribe to live OHLCV → on each
  completed bar, build MarketWindow, call strategy, fill orders.

State is persisted to a JSONL trade journal at `./paper-journal/<strategy_id>.jsonl`
so paper P&L can be reconciled against expected P&L day-by-day.

Phase 0 status: scaffolding + interfaces. The websocket-driven loop wires
to Phase 1 ingest in the next commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

from janus.backtest.metrics import TradeRecord
from janus.backtest.slippage import SlippageModel, SquareRootImpactSlippage
from janus.strategies.base import Order, OrderIntent, Position, Side


@dataclass(slots=True)
class PaperFill:
    client_order_id: UUID
    fill_price: Decimal
    qty: Decimal
    ts: datetime
    slippage_bps: float


@dataclass(slots=True)
class PaperBroker:
    """In-memory broker that mimics the live broker's surface."""

    slippage: SlippageModel = field(default_factory=SquareRootImpactSlippage)
    cash: Decimal = Decimal("100000")
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: Decimal = Decimal(0)
    fills: list[PaperFill] = field(default_factory=list)
    trades: list[TradeRecord] = field(default_factory=list)

    def submit(self, order: Order, mark: Decimal, ctx: dict[str, Any], ts: datetime) -> PaperFill:
        side = "long" if order.side is Side.LONG else "short"
        fill = self.slippage.fill(side=side, mark=mark, qty=order.qty, ctx=ctx)

        if order.intent is OrderIntent.OPEN:
            self.cash -= fill.fill_price * order.qty
            self.positions[order.symbol] = Position(
                symbol=order.symbol, side=order.side, qty=order.qty,
                avg_entry_price=fill.fill_price, opened_at=ts,
                strategy_id=order.strategy_id,
                take_profit=order.take_profit, stop_loss=order.stop_loss,
            )
        else:
            existing = self.positions.pop(order.symbol, None)
            if existing is not None:
                sign = Decimal(1) if existing.side is Side.LONG else Decimal(-1)
                pnl = (fill.fill_price - existing.avg_entry_price) * existing.qty * sign
                self.cash += fill.fill_price * existing.qty
                self.realized_pnl += pnl
                self.trades.append(TradeRecord(
                    pnl_quote=float(pnl),
                    return_pct=float(pnl / (existing.avg_entry_price * existing.qty)),
                    entry_ts_utc_minute=int(existing.opened_at.timestamp() // 60),
                    exit_ts_utc_minute=int(ts.timestamp() // 60),
                ))

        paper_fill = PaperFill(
            client_order_id=order.client_order_id,
            fill_price=fill.fill_price,
            qty=order.qty,
            ts=ts,
            slippage_bps=fill.slippage_bps,
        )
        self.fills.append(paper_fill)
        return paper_fill


def append_journal(path: Path, record: dict[str, Any]) -> None:
    """JSON-Lines append. One line per trade — easy to grep + audit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


@dataclass(slots=True)
class PaperRunner:
    """Wraps a strategy + broker and drives them with live OHLCV.

    The full live-driven loop is added in the engine batch; this scaffolds the
    contract so PaperBroker can already be unit-tested independently.
    """

    broker: PaperBroker
    journal_dir: Path = Path("./paper-journal")

    def record_fill(self, strategy_id: str, fill: PaperFill, order: Order) -> None:
        path = self.journal_dir / f"{strategy_id}.jsonl"
        append_journal(path, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "fill_ts": fill.ts.isoformat(),
            "strategy_id": strategy_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "intent": order.intent.value,
            "qty": str(order.qty),
            "fill_price": str(fill.fill_price),
            "slippage_bps": fill.slippage_bps,
            "signal": order.signal.name if order.signal else None,
            "client_order_id": str(order.client_order_id),
        })
        logger.bind(strategy=strategy_id, symbol=order.symbol).info(
            "paper fill {} qty={} @ {} slip={:.1f}bps",
            order.intent.value, order.qty, fill.fill_price, fill.slippage_bps,
        )
