# Railway-deployable TimescaleDB image.
# Railway's stock Postgres doesn't have the timescaledb extension, so spin up
# a custom service from this Dockerfile. Volume-back the data dir from
# Railway's persistent volume.
FROM timescale/timescaledb:2.15.0-pg16

# Telemetry off — Janus is a private deployment.
ENV TS_TUNE_TELEMETRY=off
ENV TIMESCALEDB_TELEMETRY=off

# Default bind. Railway maps $PORT but Postgres uses 5432 internally;
# the service exposes the *internal* port. Other Railway services
# connect via the auto-injected DATABASE_URL.
EXPOSE 5432
