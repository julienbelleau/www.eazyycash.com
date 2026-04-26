"""Stablecoin feature tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from janus.features.stablecoin_features import (
    StablecoinSnapshot,
    btc_inflow_ratio,
    cex_dex_peg_arb_spread_bps,
    funding_already_priced,
    funding_term_structure,
    is_solvability_concern,
    issuer_treasury_ratio,
    pair_volume_ratio,
    peg_deviation_bps,
    pool_depth_severity,
    volume_anomaly_ratio,
)


def _snap(**kw: object) -> StablecoinSnapshot:
    base = dict(
        asset="USDC", as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        cex_price_usd=Decimal("1.0"), dex_price_usd=Decimal("1.0"),
        pool_depth_usd=Decimal("500000000"),
        issuer_cash_equivalents_usd=Decimal("103000000000"),
        issuer_total_liabilities_usd=Decimal("100000000000"),
        cex_volume_24h_usd=Decimal("100000000"),
        cex_volume_24h_baseline=Decimal("80000000"),
        btc_exchange_inflow_btc=Decimal("100"),
        btc_exchange_inflow_baseline=Decimal("80"),
        btc_pair_volume_btcusdt=Decimal("60"),
        btc_pair_volume_btcusdc=Decimal("40"),
        funding_1h=Decimal("0.0001"),
        funding_8h=Decimal("0.00012"),
        funding_24h=Decimal("0.00014"),
    )
    base.update(kw)
    return StablecoinSnapshot(**base)  # type: ignore[arg-type]


def test_peg_deviation_zero_when_at_peg() -> None:
    snap = _snap()
    assert peg_deviation_bps(snap, source="cex") == 0.0
    assert peg_deviation_bps(snap, source="dex") == 0.0


def test_peg_deviation_positive_for_below_peg() -> None:
    snap = _snap(dex_price_usd=Decimal("0.997"))
    # 0.3% off → 30 bps
    assert abs(peg_deviation_bps(snap, source="dex") - 30.0) < 1e-6


def test_cex_dex_arb_spread_signed() -> None:
    snap = _snap(cex_price_usd=Decimal("1.001"), dex_price_usd=Decimal("0.997"))
    spread = cex_dex_peg_arb_spread_bps(snap)
    assert spread > 0


def test_pool_depth_severity_inverse_to_depth() -> None:
    deep = _snap(pool_depth_usd=Decimal("1000000000"))
    shallow = _snap(pool_depth_usd=Decimal("100000000"))
    assert pool_depth_severity(shallow) > pool_depth_severity(deep)


def test_pool_depth_severity_capped() -> None:
    tiny = _snap(pool_depth_usd=Decimal("1"))
    assert pool_depth_severity(tiny) == 5.0
    zero = _snap(pool_depth_usd=Decimal("0"))
    assert pool_depth_severity(zero) == 5.0


def test_treasury_ratio() -> None:
    snap = _snap()
    assert abs((issuer_treasury_ratio(snap) or 0) - 1.03) < 1e-9
    snap_unknown = _snap(issuer_cash_equivalents_usd=None)
    assert issuer_treasury_ratio(snap_unknown) is None


def test_solvability_concern_predicate() -> None:
    healthy = _snap()
    assert is_solvability_concern(healthy) is False
    weak = _snap(issuer_cash_equivalents_usd=Decimal("100000000000"),
                 issuer_total_liabilities_usd=Decimal("105000000000"))
    assert is_solvability_concern(weak) is True
    unknown = _snap(issuer_cash_equivalents_usd=None)
    assert is_solvability_concern(unknown) is None


def test_volume_anomaly_ratio() -> None:
    assert volume_anomaly_ratio(_snap()) == 1.25


def test_btc_inflow_ratio() -> None:
    assert btc_inflow_ratio(_snap()) == 1.25


def test_pair_volume_ratio() -> None:
    assert pair_volume_ratio(_snap()) == 0.6


def test_funding_term_structure_levels_and_slopes() -> None:
    ts = funding_term_structure(_snap())
    assert ts["level_1h"] == 0.0001
    assert ts["slope_short"] > 0
    assert ts["slope_long"] > 0


def test_funding_already_priced_blocks_when_steep() -> None:
    snap_priced = _snap(funding_1h=Decimal("0.0001"), funding_8h=Decimal("0.001"),
                         funding_24h=Decimal("0.002"))
    assert funding_already_priced(snap_priced)
    snap_flat = _snap(funding_1h=Decimal("0"), funding_8h=Decimal("0"),
                       funding_24h=Decimal("0"))
    assert not funding_already_priced(snap_flat)
