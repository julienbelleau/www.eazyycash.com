"""Settings should fail-fast on misconfiguration."""

from __future__ import annotations

import pytest

from janus.config.settings import Environment, Settings, reset_settings_cache


def test_default_settings_load_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JANUS_ENV", "dev")
    reset_settings_cache()
    s = Settings()
    assert s.env is Environment.DEV
    assert s.database.async_dsn.startswith("postgresql+asyncpg://")


def test_live_env_without_creds_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JANUS_ENV", "live")
    monkeypatch.setenv("BINANCE_API_KEY", "")
    monkeypatch.setenv("BINANCE_API_SECRET", "")
    reset_settings_cache()
    with pytest.raises(ValueError, match="BINANCE_API_KEY"):
        Settings()


def test_redis_url_with_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    reset_settings_cache()
    s = Settings()
    assert "secret@" in s.redis.url


def test_redis_url_without_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    reset_settings_cache()
    s = Settings()
    assert "@" not in s.redis.url
