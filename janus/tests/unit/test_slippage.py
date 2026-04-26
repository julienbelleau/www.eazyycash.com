"""Slippage model tests."""

from __future__ import annotations

from decimal import Decimal

from janus.backtest.slippage import OrderbookWalkSlippage, SquareRootImpactSlippage


def test_orderbook_walk_long_eats_best_ask_first() -> None:
    book = {"asks": [[40_010, 1.0], [40_020, 5.0], [40_050, 10.0]],
            "bids": [[39_990, 1.0]]}
    s = OrderbookWalkSlippage(fee_bps=4.0)
    fill = s.fill(side="long", mark=Decimal("40000"), qty=Decimal("0.5"), ctx=book)
    # Should fill entirely from best ask.
    assert fill.fully_filled
    # ~25 bps offset from mark + 4 bps fees ≈ 29 bps total.
    assert 25.0 <= fill.slippage_bps <= 35.0


def test_orderbook_walk_long_walks_multiple_levels() -> None:
    book = {"asks": [[40_010, 1.0], [40_500, 2.0]], "bids": [[39_990, 1.0]]}
    s = OrderbookWalkSlippage(fee_bps=4.0)
    fill = s.fill(side="long", mark=Decimal("40000"), qty=Decimal("2.5"), ctx=book)
    # 1 BTC at 40010 + 1.5 BTC at 40500 = (40010 + 60750) / 2.5 = 40_304
    avg = (Decimal("40010") * Decimal("1") + Decimal("40500") * Decimal("1.5")) / Decimal("2.5")
    expected_pre_fee = avg
    # After fee, ~ avg * (1 + 0.0004)
    assert fill.fill_price > expected_pre_fee
    assert fill.fully_filled


def test_orderbook_walk_short_uses_bids() -> None:
    book = {"asks": [[40_100, 1.0]], "bids": [[39_990, 0.5], [39_950, 5.0]]}
    s = OrderbookWalkSlippage(fee_bps=4.0)
    fill = s.fill(side="short", mark=Decimal("40000"), qty=Decimal("1.0"), ctx=book)
    assert fill.fully_filled
    # Short fill price should be below mark.
    assert fill.fill_price < Decimal("40000")


def test_orderbook_walk_partial_fill_when_book_thin() -> None:
    book = {"asks": [[40_010, 0.1]], "bids": []}
    s = OrderbookWalkSlippage()
    fill = s.fill(side="long", mark=Decimal("40000"), qty=Decimal("1.0"), ctx=book)
    assert not fill.fully_filled


def test_orderbook_walk_no_book_falls_back() -> None:
    s = OrderbookWalkSlippage()
    fill = s.fill(side="long", mark=Decimal("40000"), qty=Decimal("1.0"), ctx={})
    assert fill.slippage_bps == 50.0


def test_sqrt_impact_scales_with_size() -> None:
    s = SquareRootImpactSlippage(eta=0.5, sigma_intraday=0.02, fee_bps=0.0,
                                  adv_quote=10_000_000.0)
    small = s.fill(side="long", mark=Decimal("40000"), qty=Decimal("0.01"), ctx={})
    big = s.fill(side="long", mark=Decimal("40000"), qty=Decimal("10.0"), ctx={})
    assert big.slippage_bps > small.slippage_bps
    # Sqrt-scaling: 1000× notional → ~31× slippage.
    assert big.slippage_bps > small.slippage_bps * 5


def test_sqrt_impact_fee_added_on_top() -> None:
    s_no_fee = SquareRootImpactSlippage(fee_bps=0.0)
    s_with_fee = SquareRootImpactSlippage(fee_bps=10.0)
    a = s_no_fee.fill(side="long", mark=Decimal("40000"), qty=Decimal("0.1"), ctx={})
    b = s_with_fee.fill(side="long", mark=Decimal("40000"), qty=Decimal("0.1"), ctx={})
    assert abs(b.slippage_bps - a.slippage_bps - 10.0) < 1e-6
