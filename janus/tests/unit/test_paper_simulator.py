"""Paper broker tests — the in-memory broker that mirrors the live API."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from janus.backtest.slippage import SquareRootImpactSlippage
from janus.paper.simulator import PaperBroker, PaperRunner
from janus.strategies.base import Order, OrderIntent, OrderType, Side


def test_paper_broker_open_then_close_realises_pnl(tmp_path: Path) -> None:
    broker = PaperBroker(slippage=SquareRootImpactSlippage(fee_bps=0.0,
                                                           sigma_intraday=0.0,
                                                           eta=0.0))
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

    open_order = Order(
        strategy_id="x", symbol="BTCUSDT",
        side=Side.LONG, intent=OrderIntent.OPEN,
        qty=Decimal("0.1"), order_type=OrderType.MARKET,
    )
    fill_open = broker.submit(open_order, mark=Decimal("40000"), ctx={}, ts=ts)
    assert fill_open.fill_price == Decimal("40000")
    assert "BTCUSDT" in broker.positions

    close_order = Order(
        strategy_id="x", symbol="BTCUSDT",
        side=Side.LONG, intent=OrderIntent.CLOSE,
        qty=Decimal("0.1"), order_type=OrderType.MARKET,
    )
    broker.submit(close_order, mark=Decimal("42000"), ctx={}, ts=ts)

    # +2000 USD/BTC * 0.1 BTC = 200 USD realised.
    assert broker.realized_pnl == Decimal("200")
    assert "BTCUSDT" not in broker.positions
    assert len(broker.trades) == 1
    assert broker.trades[0].pnl_quote == 200.0


def test_runner_writes_journal(tmp_path: Path) -> None:
    broker = PaperBroker(slippage=SquareRootImpactSlippage(fee_bps=0.0))
    runner = PaperRunner(broker=broker, journal_dir=tmp_path)
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    order = Order(
        strategy_id="x", symbol="BTCUSDT",
        side=Side.LONG, intent=OrderIntent.OPEN,
        qty=Decimal("0.1"), order_type=OrderType.MARKET,
    )
    fill = broker.submit(order, mark=Decimal("40000"), ctx={}, ts=ts)
    runner.record_fill("x", fill, order)
    journal = (tmp_path / "x.jsonl")
    assert journal.exists()
    contents = journal.read_text()
    assert "BTCUSDT" in contents
    assert "open" in contents
