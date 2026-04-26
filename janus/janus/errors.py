"""Janus exception taxonomy.

Trading systems must distinguish between *transient* errors (retry safe) and
*permanent* errors (require human intervention). Generic `Exception`-everywhere
makes that distinction impossible — hence the explicit hierarchy.

Conventions:
- `TransientError` and subclasses are caught by retry decorators.
- `PermanentError` and subclasses always escalate (kill switch / alert).
- Each error carries a stable `code` for log filtering and Prometheus labels.
"""

from __future__ import annotations


class JanusError(Exception):
    """Base for all Janus errors."""

    code: str = "janus.unknown"


# ─────────────────────────── transient ───────────────────────────

class TransientError(JanusError):
    """Retry safely after backoff — network blips, rate limits, transient 5xx."""

    code = "janus.transient"


class RateLimitedError(TransientError):
    code = "janus.rate_limited"


class ExchangeUnavailableError(TransientError):
    code = "janus.exchange_unavailable"


class WebSocketDisconnected(TransientError):
    code = "janus.ws_disconnected"


# ─────────────────────────── permanent ───────────────────────────

class PermanentError(JanusError):
    """Escalate — auth failures, schema violations, kill-switch triggers."""

    code = "janus.permanent"


class AuthError(PermanentError):
    code = "janus.auth"


class ConfigError(PermanentError):
    code = "janus.config"


class SchemaViolation(PermanentError):
    code = "janus.schema_violation"


class ClockDriftError(PermanentError):
    """Local clock drifts beyond tolerance — point-in-time correctness is at risk."""

    code = "janus.clock_drift"


class DataQualityViolation(PermanentError):
    """A data-quality invariant was violated (gap, OHLC sanity, cross-source mismatch).

    Carries structured context (rule + detail) so the violation is filterable in logs.
    """

    code = "janus.data_quality"

    def __init__(self, rule: str, detail: str) -> None:
        super().__init__(f"[{rule}] {detail}")
        self.rule = rule
        self.detail = detail
