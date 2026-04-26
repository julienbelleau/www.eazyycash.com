"""FastAPI app + auth tests.

We don't talk to a real DB here — `get_session` and `get_tenant_context`
are dependency-overridden in the test client so the routes can exercise
their request/response contracts deterministically.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
import pytest
from asgi_lifespan import LifespanManager

from janus.api.auth import TenantContext, get_tenant_context
from janus.api.db import get_session
from janus.api.main import create_app
from janus.api.routes.strategies import get_registry
from janus.config.settings import Settings, reset_settings_cache
from janus.risk.kill_switches import KillScope, KillSwitchRegistry
from janus.saas.tenant import ApiKeyRecord, Tenant


def _make_ctx(scopes: tuple[str, ...] = ("read", "write", "admin")) -> TenantContext:
    return TenantContext(
        tenant=Tenant(id="t1", name="acme", plan="free"),
        api_key=ApiKeyRecord(
            id="k1", tenant_id="t1", short_id="abcdefgh",
            hashed_secret="0", label="test", scopes=scopes,
            expires_at=None, revoked=False,
        ),
        request_id="r1",
    )


@pytest.fixture()
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    reset_settings_cache()
    app = create_app(settings=Settings())

    # Override DB session — none of the routes we test need it.
    async def _noop_session() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_session] = _noop_session
    app.dependency_overrides[get_tenant_context] = lambda: _make_ctx()
    # Fresh registry per test.
    app.dependency_overrides[get_registry] = lambda: KillSwitchRegistry()

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                      base_url="http://test") as c:
            yield c


@pytest.mark.asyncio()
async def test_healthz_returns_ok(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio()
async def test_root_documents_endpoints(client: httpx.AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["docs"] == "/docs"


@pytest.mark.asyncio()
async def test_strategies_list_default_state(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/strategies")
    assert r.status_code == 200
    body = r.json()
    assert {s["id"] for s in body} == {
        "refractory_v1", "narrative_rotation_v1", "stablecoin_stress_v1",
    }
    assert all(s["paused"] is False for s in body)


@pytest.mark.asyncio()
async def test_pause_then_resume_strategy(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/v1/strategies/refractory_v1/pause",
        json={"reason": "manual investigation"},
    )
    assert r.status_code == 200
    assert "paused_at" in r.json()

    r = await client.get("/v1/strategies")
    refr = next(s for s in r.json() if s["id"] == "refractory_v1")
    assert refr["paused"] is True
    assert "investigation" in refr["paused_reason"]

    r = await client.post("/v1/strategies/refractory_v1/resume")
    assert r.status_code == 200

    r = await client.get("/v1/strategies")
    refr = next(s for s in r.json() if s["id"] == "refractory_v1")
    assert refr["paused"] is False


@pytest.mark.asyncio()
async def test_unknown_strategy_returns_404(client: httpx.AsyncClient) -> None:
    r = await client.post("/v1/strategies/nope/pause", json={"reason": "x"})
    assert r.status_code == 404


@pytest.mark.asyncio()
async def test_regime_endpoint_shape(client: httpx.AsyncClient) -> None:
    r = await client.get("/v1/regime")
    assert r.status_code == 200
    body = r.json()
    assert "regime" in body
    assert "weights" in body
    assert set(body["weights"].keys()) == {
        "refractory_v1", "narrative_rotation_v1", "stablecoin_stress_v1",
    }


@pytest.mark.asyncio()
async def test_portfolio_summary_shape(client: httpx.AsyncClient,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    # The route hits session.execute("SELECT NOW()"). We didn't override the
    # session fully — monkeypatch the underlying engine call.
    from janus.api.routes import portfolio as pmod
    async def _stub(*args: object, **kwargs: object) -> object:
        class _Result:
            def scalar(self) -> datetime:
                return datetime(2024, 1, 1, tzinfo=timezone.utc)
        return _Result()
    monkeypatch.setattr("janus.api.routes.portfolio.text", lambda s: s)

    # Override session with one whose execute returns the stub.
    class _S:
        async def execute(self, *a: object, **k: object) -> object:
            return await _stub()
        async def close(self) -> None: ...
    async def _yields() -> object:
        yield _S()
    pmod_app = client._transport.app  # type: ignore[attr-defined]
    pmod_app.dependency_overrides[get_session] = _yields

    r = await client.get("/v1/portfolio/summary")
    assert r.status_code == 200
    assert r.json()["tenant_id"] == "t1"


@pytest.mark.asyncio()
async def test_auth_required_when_dependency_not_overridden() -> None:
    """An app without the auth override must reject unauthenticated requests."""
    reset_settings_cache()
    app = create_app(settings=Settings())

    async def _noop_session() -> AsyncIterator[None]:
        yield None
    app.dependency_overrides[get_session] = _noop_session

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                      base_url="http://test") as c:
            r = await c.get("/v1/strategies")
            assert r.status_code == 401
