"""API server entrypoint (alternative to direct uvicorn invocation).

Both forms work on Railway; uvicorn-direct is preferred (lower memory).
This script exists for: local dev, debugging, and ops who want to see
exactly which settings booted the process.
"""

from __future__ import annotations

import sys

import uvicorn

from janus.config.settings import get_settings
from janus.monitoring.logging_config import configure_logging


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    uvicorn.run(
        "janus.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        workers=settings.api.workers,
        log_config=None,   # we own logging via loguru
        access_log=False,  # logged via RequestContextMiddleware
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
