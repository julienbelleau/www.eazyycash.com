"""One-shot bootstrap: ensure the timescaledb extension exists, then alembic upgrade head.

Usage:
    poetry run python scripts/init_db.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from janus.config.settings import get_settings
from janus.monitoring.logging_config import configure_logging


async def _ensure_extension() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database.async_dsn, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
    await engine.dispose()


def _run_migrations() -> None:
    cfg_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(cfg_path))
    command.upgrade(cfg, "head")


async def main() -> int:
    configure_logging()
    logger.info("ensuring timescaledb extension")
    await _ensure_extension()
    logger.info("running alembic upgrade head")
    _run_migrations()
    logger.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
