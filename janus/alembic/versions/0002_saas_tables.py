"""SaaS tables: tenants + api_keys.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenants (
            id           VARCHAR(32) PRIMARY KEY,
            name         VARCHAR(128) NOT NULL,
            plan         VARCHAR(32) NOT NULL DEFAULT 'free',
            created_at   TIMESTAMPTZ NOT NULL,
            disabled_at  TIMESTAMPTZ,
            CONSTRAINT uq_tenants_name UNIQUE (name)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE api_keys (
            id              VARCHAR(32) PRIMARY KEY,
            tenant_id       VARCHAR(32) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            short_id        VARCHAR(16) NOT NULL,
            hashed_secret   VARCHAR(64) NOT NULL,
            label           VARCHAR(128) NOT NULL DEFAULT '',
            scopes          VARCHAR(512) NOT NULL DEFAULT 'read',
            created_at      TIMESTAMPTZ NOT NULL,
            last_used_at    TIMESTAMPTZ,
            expires_at      TIMESTAMPTZ,
            revoked_at      TIMESTAMPTZ,
            CONSTRAINT uq_api_keys_short_id UNIQUE (short_id)
        );
        CREATE INDEX ix_api_keys_tenant_id ON api_keys(tenant_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_keys CASCADE;")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE;")
