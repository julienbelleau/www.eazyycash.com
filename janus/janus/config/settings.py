"""Typed runtime configuration for Janus.

All settings come from environment variables (validated by pydantic-settings)
or, in tests, from explicit overrides. There is intentionally no module-level
mutable state — every consumer calls `get_settings()`, which is cached.

Why fail-fast: a trading process with a missing API key or wrong DSN should
crash at startup, not three hours into a backtest.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    PAPER = "paper"
    LIVE = "live"


def _parse_dsn(dsn: str) -> dict[str, str | int]:
    """Parse a postgres:// or redis:// URL into component fields.

    Railway injects DATABASE_URL / REDIS_URL on service link; we accept both
    the classic POSTGRES_* env vars and the URL form.
    """
    parsed = urlparse(dsn)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "db": (parsed.path or "/").lstrip("/"),
    }


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    db: str = "janus"
    user: str = "janus"
    password: SecretStr = SecretStr("janus_dev")

    @model_validator(mode="before")
    @classmethod
    def _hydrate_from_url(cls, values: dict[str, object] | None) -> dict[str, object]:
        # Railway / Heroku-style: DATABASE_URL takes precedence when present.
        url = os.getenv("DATABASE_URL")
        if not url:
            return values or {}
        parts = _parse_dsn(url)
        # Don't override explicit POSTGRES_* values (lets dev override the URL).
        merged = dict(values or {})
        for k, v in parts.items():
            merged.setdefault(k, v)
        return merged

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:"
            f"{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_dsn(self) -> str:
        # Used by Alembic — Alembic does not support asyncpg directly.
        return (
            f"postgresql+psycopg2://{self.user}:"
            f"{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        )


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr = SecretStr("")

    @model_validator(mode="before")
    @classmethod
    def _hydrate_from_url(cls, values: dict[str, object] | None) -> dict[str, object]:
        url = os.getenv("REDIS_URL")
        if not url:
            return values or {}
        parts = _parse_dsn(url)
        merged = dict(values or {})
        for k, v in parts.items():
            if k == "db":
                merged.setdefault(k, int(v) if v else 0)
            elif k == "port":
                merged.setdefault(k, v if v else 6379)
            else:
                merged.setdefault(k, v)
        return merged

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        pwd = self.password.get_secret_value()
        auth = f":{pwd}@" if pwd else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class BinanceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BINANCE_", extra="ignore")

    api_key: SecretStr = SecretStr("")
    api_secret: SecretStr = SecretStr("")
    testnet: bool = False

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key.get_secret_value() and self.api_secret.get_secret_value())


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    sentry_dsn: SecretStr = Field(default=SecretStr(""), validation_alias="SENTRY_DSN")
    telegram_bot_token: SecretStr = Field(
        default=SecretStr(""), validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_chat_id: str = Field(default="", validation_alias="TELEGRAM_CHAT_ID")
    prometheus_port: int = Field(default=9090, validation_alias="PROMETHEUS_PORT")


class ApiSettings(BaseSettings):
    """SaaS web API runtime config."""

    model_config = SettingsConfigDict(env_prefix="JANUS_API_", extra="ignore")

    # Railway injects PORT — bind to it. 8000 is the local default.
    port: int = Field(default=8000, validation_alias="PORT")
    host: str = "0.0.0.0"  # noqa: S104 — required for container deployments
    workers: int = 1
    cors_allow_origins: str = "*"   # comma-separated; tighten for prod
    rate_limit_per_minute: int = 120
    # Pepper used when hashing API keys; rotate by setting a new one and
    # invalidating tokens (forces re-issuance).
    api_key_pepper: SecretStr = SecretStr("janus_dev_pepper_change_me")
    public_base_url: str = ""        # set by Railway: https://service.up.railway.app
    request_id_header: str = "x-request-id"


class Settings(BaseSettings):
    """Top-level settings aggregator. Exactly one instance per process."""

    model_config = SettingsConfigDict(
        env_prefix="JANUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: Environment = Environment.DEV
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True
    random_seed: int = 42

    # Tolerance for clock drift before we refuse to start ingestion (seconds).
    # 2s is generous; live trading should target <500ms via NTP/chrony.
    max_clock_drift_seconds: float = 2.0

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    binance: BinanceSettings = Field(default_factory=BinanceSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    api: ApiSettings = Field(default_factory=ApiSettings)

    enable_live_tests: bool = Field(default=False, validation_alias="JANUS_ENABLE_LIVE_TESTS")

    @model_validator(mode="after")
    def _live_must_have_creds(self) -> "Settings":
        # In live mode we require Binance creds — refuse to boot otherwise.
        if self.env is Environment.LIVE and not self.binance.has_credentials:
            raise ValueError(
                "JANUS_ENV=live requires BINANCE_API_KEY and BINANCE_API_SECRET to be set."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton (cached)."""
    return Settings()


def reset_settings_cache() -> None:
    """Test-only: drop the cache so a new env can be picked up between tests."""
    get_settings.cache_clear()
