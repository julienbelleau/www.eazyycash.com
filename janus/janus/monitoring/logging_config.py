"""Structured logging via loguru.

Decisions:
- JSON output in prod/paper for machine parsability; pretty in dev for humans.
- We patch the root stdlib logger so libraries (sqlalchemy, ccxt) flow into loguru.
- A `bind(...)` context is created per ingestion job / per strategy run so every
  log line is attributable post-hoc — required for the "every trade explainable"
  invariant in JANUS_TRADING_SYSTEM_PLAN.md §0.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger

from janus.config.settings import Settings, get_settings


class _InterceptHandler(logging.Handler):
    """Forward stdlib logging records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - thin shim
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(settings: Settings | None = None) -> None:
    """Configure loguru. Idempotent — safe to call multiple times in tests."""
    settings = settings or get_settings()

    logger.remove()

    if settings.log_json:
        # serialize=True emits one JSON object per log line; ingest-friendly.
        logger.add(
            sys.stderr,
            level=settings.log_level,
            serialize=True,
            backtrace=False,
            diagnose=False,
            enqueue=True,
        )
    else:
        logger.add(
            sys.stderr,
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
                "<level>{level: <8}</level> "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
                "{extra} <level>{message}</level>"
            ),
        )

    # Bridge stdlib loggers into loguru (ccxt, sqlalchemy, asyncio…).
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("sqlalchemy.engine", "ccxt", "asyncio", "httpx", "httpcore"):
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = [_InterceptHandler()]
        stdlib_logger.propagate = False


def bind_context(**kwargs: Any) -> "logger.__class__":  # type: ignore[name-defined]
    """Return a logger bound with extra context (job_id, symbol, strategy…)."""
    return logger.bind(**kwargs)
