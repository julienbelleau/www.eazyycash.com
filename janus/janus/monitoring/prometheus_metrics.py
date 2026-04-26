"""Prometheus metrics — Counters / Gauges / Histograms used by Janus.

The metrics are defined as module-level objects so they're singletons across
the process. Calling them is `metric.labels(...).inc()` etc.

A single `start_http_server()` call exposes /metrics on the configured port
(see janus.config.settings.observability.prometheus_port).
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)


REGISTRY = CollectorRegistry()


# ─── ingestion ───
ingest_jobs_total = Counter(
    "janus_ingest_jobs_total",
    "Number of ingest jobs by source/dataset/status",
    ["source", "dataset", "status"],
    registry=REGISTRY,
)

ingest_rows_total = Counter(
    "janus_ingest_rows_total",
    "Total rows ingested",
    ["source", "dataset"],
    registry=REGISTRY,
)


# ─── trading ───
orders_submitted_total = Counter(
    "janus_orders_submitted_total",
    "Orders submitted by strategy/side/intent",
    ["strategy", "side", "intent"],
    registry=REGISTRY,
)

trades_closed_total = Counter(
    "janus_trades_closed_total",
    "Closed trades by strategy/outcome",
    ["strategy", "outcome"],   # outcome = win | loss | flat
    registry=REGISTRY,
)

realised_pnl_quote = Counter(
    "janus_realised_pnl_quote_total",
    "Realised P&L per strategy in quote currency",
    ["strategy"],
    registry=REGISTRY,
)

position_count = Gauge(
    "janus_open_positions",
    "Currently-open positions per strategy",
    ["strategy"],
    registry=REGISTRY,
)

portfolio_equity = Gauge(
    "janus_portfolio_equity_quote",
    "Portfolio equity in quote currency",
    registry=REGISTRY,
)


# ─── execution ───
slippage_bps = Histogram(
    "janus_slippage_bps",
    "Realised slippage in basis points",
    ["strategy", "symbol"],
    buckets=(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000),
    registry=REGISTRY,
)

order_latency_seconds = Histogram(
    "janus_order_latency_seconds",
    "Time between submit and fill",
    ["exchange"],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=REGISTRY,
)


# ─── kill switches / health ───
kill_switch_active = Gauge(
    "janus_kill_switch_active",
    "1 if a kill switch is active for the (scope, target)",
    ["scope", "target"],
    registry=REGISTRY,
)

regime_state = Gauge(
    "janus_regime_state",
    "Current regime as enum-coded integer (1=bull,2=bear,3=range,4=crisis,5=recovery)",
    registry=REGISTRY,
)


def start_metrics_server(port: int) -> None:
    start_http_server(port, registry=REGISTRY)
