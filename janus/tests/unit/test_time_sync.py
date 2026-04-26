"""Clock drift detection — uses respx to mock the Binance time endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from janus.config.settings import Settings
from janus.errors import ClockDriftError, ExchangeUnavailableError
from janus.time_sync import assert_clock_in_sync, measure_clock_drift


@pytest.mark.asyncio()
async def test_clock_in_sync(respx_mock: respx.Router) -> None:
    server_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    respx_mock.get("https://api.binance.com/api/v3/time").mock(
        return_value=httpx.Response(200, json={"serverTime": server_ms})
    )
    s = Settings(max_clock_drift_seconds=5.0)
    report = await assert_clock_in_sync(s)
    assert abs(report.drift_seconds) < 5.0


@pytest.mark.asyncio()
async def test_clock_drift_detected(respx_mock: respx.Router) -> None:
    # Simulate the server clock running 10s ahead.
    server_ms = int((datetime.now(timezone.utc) + timedelta(seconds=10)).timestamp() * 1000)
    respx_mock.get("https://api.binance.com/api/v3/time").mock(
        return_value=httpx.Response(200, json={"serverTime": server_ms})
    )
    s = Settings(max_clock_drift_seconds=2.0)
    with pytest.raises(ClockDriftError, match="exceeds tolerance"):
        await assert_clock_in_sync(s)


@pytest.mark.asyncio()
async def test_clock_endpoint_5xx_raises_transient(respx_mock: respx.Router) -> None:
    respx_mock.get("https://api.binance.com/api/v3/time").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )
    with pytest.raises(ExchangeUnavailableError):
        await measure_clock_drift()
