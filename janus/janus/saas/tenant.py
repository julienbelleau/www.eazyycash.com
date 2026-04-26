"""Tenant + ApiKey domain.

Janus is single-tenant by default but the architecture is multi-tenant-ready:
  * Every SaaS-relevant table can carry a `tenant_id` (Phase 2 of SaaS-ification).
  * ApiKeys are scoped to a tenant.
  * Auth resolves a request to a tenant context that downstream code can
    use to filter queries.

API key model:
  * The plaintext key is shown ONCE at creation (`jns_<short_id>_<secret>`).
  * Only an HMAC-SHA256 of (peppered, secret) is stored in the DB.
  * `short_id` is searchable so we can identify which key authenticated a
    request without storing the secret.
  * Keys can be revoked (soft delete) and have an optional expiry.

The pepper lives in `Settings.api.api_key_pepper` (env: `JANUS_API_API_KEY_PEPPER`).
Rotating the pepper invalidates every existing key — by design.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    text,
)

from janus.data.schema.models import metadata


# ─────────────────────────── tables ───────────────────────────

tenants = Table(
    "tenants",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("name", String(128), nullable=False),
    Column("plan", String(32), nullable=False, server_default=text("'free'")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("disabled_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("name", name="uq_tenants_name"),
)


api_keys = Table(
    "api_keys",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("tenant_id", String(32), nullable=False),
    Column("short_id", String(16), nullable=False),
    Column("hashed_secret", String(64), nullable=False),  # sha256 hex
    Column("label", String(128), nullable=False, server_default=text("''")),
    Column("scopes", String(512), nullable=False, server_default=text("'read'")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_used_at", DateTime(timezone=True), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Index("ix_api_keys_tenant_id", "tenant_id"),
    UniqueConstraint("short_id", name="uq_api_keys_short_id"),
)


# ─────────────────────────── key generation / verification ───────────────────────────

KEY_PREFIX = "jns_"
SHORT_ID_LEN = 8
SECRET_LEN = 32


@dataclass(frozen=True, slots=True)
class GeneratedKey:
    """Returned at creation time — the only moment the plaintext exists."""

    plaintext: str
    short_id: str
    hashed_secret: str

    def __str__(self) -> str:
        return self.plaintext


def _hash_secret(pepper: str, short_id: str, secret: str) -> str:
    """HMAC-SHA256 over (short_id|secret) with the configured pepper as the key."""
    msg = f"{short_id}.{secret}".encode("utf-8")
    return hmac.new(pepper.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def generate_api_key(pepper: str) -> GeneratedKey:
    """Create a new API key. Show plaintext to the user; store only the hash."""
    short_id = secrets.token_urlsafe(SHORT_ID_LEN)[:SHORT_ID_LEN].replace("-", "x").replace("_", "y")
    secret = secrets.token_urlsafe(SECRET_LEN)
    plaintext = f"{KEY_PREFIX}{short_id}_{secret}"
    hashed = _hash_secret(pepper, short_id, secret)
    return GeneratedKey(plaintext=plaintext, short_id=short_id, hashed_secret=hashed)


def parse_api_key(plaintext: str) -> tuple[str, str] | None:
    """Split `jns_<short>_<secret>` → (short_id, secret). Returns None on bad shape."""
    if not plaintext.startswith(KEY_PREFIX):
        return None
    body = plaintext[len(KEY_PREFIX):]
    parts = body.split("_", 1)
    if len(parts) != 2 or len(parts[0]) != SHORT_ID_LEN or len(parts[1]) < 8:
        return None
    return parts[0], parts[1]


def verify_api_key(*, plaintext: str, expected_hash: str, pepper: str) -> bool:
    parsed = parse_api_key(plaintext)
    if parsed is None:
        return False
    short_id, secret = parsed
    candidate = _hash_secret(pepper, short_id, secret)
    return hmac.compare_digest(candidate, expected_hash)


# ─────────────────────────── lightweight DTOs ───────────────────────────

@dataclass(frozen=True, slots=True)
class Tenant:
    id: str
    name: str
    plan: str = "free"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class ApiKeyRecord:
    id: str
    tenant_id: str
    short_id: str
    hashed_secret: str
    label: str
    scopes: tuple[str, ...]
    expires_at: datetime | None
    revoked: bool

    @property
    def is_active(self) -> bool:
        if self.revoked:
            return False
        if self.expires_at is not None and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.scopes
