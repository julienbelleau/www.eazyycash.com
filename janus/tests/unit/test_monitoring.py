"""Trade journal + telegram alerter (mocked) tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx

from janus.config.settings import Settings
from janus.monitoring.telegram_bot import TelegramAlert, TelegramAlerter
from janus.monitoring.trade_journal import JournalEntry, TradeJournal


def _entry(strategy_id: str = "x", symbol: str = "BTCUSDT") -> JournalEntry:
    return JournalEntry(
        ts=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        strategy_id=strategy_id, symbol=symbol,
        intent="open", side="long",
        qty=Decimal("0.1"), fill_price=Decimal("40000"),
        slippage_bps=4.5,
        signal_name="refractory.cascade_exhausted",
        signal_features={"velocity_pct_of_peak": 5.0},
        client_order_id=uuid4(),
    )


@pytest.mark.asyncio()
async def test_journal_round_trip(tmp_path: Path) -> None:
    j = TradeJournal(tmp_path)
    e = _entry()
    await j.append(e)
    records = j.read_day(e.ts)
    assert len(records) == 1
    assert records[0]["strategy_id"] == "x"
    assert records[0]["fill_price"] == "40000"


@pytest.mark.asyncio()
async def test_journal_filters_by_strategy(tmp_path: Path) -> None:
    j = TradeJournal(tmp_path)
    await j.append(_entry(strategy_id="x"))
    await j.append(_entry(strategy_id="y"))
    rec_x = j.read_day(datetime(2024, 1, 1, tzinfo=timezone.utc), strategy_id="x")
    assert all(r["strategy_id"] == "x" for r in rec_x)


def test_telegram_alert_format() -> None:
    a = TelegramAlert(severity="warning", title="Test", body="something")
    text = a.to_text()
    assert "Test" in text
    assert "[!]" in text


@pytest.mark.asyncio()
async def test_telegram_disabled_when_no_credentials() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    a = TelegramAlerter(settings=s)
    try:
        ok = await a.send(TelegramAlert(severity="info", title="x", body="y"))
        assert ok is False
        assert a.enabled is False
    finally:
        await a.aclose()


@pytest.mark.asyncio()
async def test_telegram_send_when_credentials_present(respx_mock: respx.Router,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc:def")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    from janus.config.settings import reset_settings_cache
    reset_settings_cache()
    s = Settings()
    respx_mock.post("https://api.telegram.org/botabc:def/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    a = TelegramAlerter(settings=s)
    try:
        ok = await a.send(TelegramAlert(severity="info", title="t", body="b"))
        assert ok is True
    finally:
        await a.aclose()
