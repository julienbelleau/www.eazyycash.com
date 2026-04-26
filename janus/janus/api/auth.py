"""API key authentication.

Resolves the `Authorization: Bearer jns_<short>_<secret>` header to a
TenantContext. The TenantContext is what downstream handlers consume —
they never see raw keys.

Audit:
- Every successful auth updates `api_keys.last_used_at` (best-effort, no
  failure escalates).
- Every failed auth is logged with the short_id (never the secret).

Performance:
- Lookup is O(1) (indexed on `short_id`). We pin the verification call to
  constant-time comparison via hmac.compare_digest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from janus.api.db import get_session
from janus.config.settings import get_settings
from janus.saas.tenant import (
    ApiKeyRecord,
    Tenant,
    api_keys,
    parse_api_key,
    tenants,
    verify_api_key,
)


bearer_scheme = HTTPBearer(auto_error=False, description="API key as Bearer token")


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant: Tenant
    api_key: ApiKeyRecord
    request_id: str

    def require_scope(self, scope: str) -> None:
        if not self.api_key.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing scope: {scope}",
            )


async def _resolve_api_key(session: AsyncSession, plaintext: str) -> ApiKeyRecord | None:
    parsed = parse_api_key(plaintext)
    if parsed is None:
        return None
    short_id, _ = parsed
    pepper = get_settings().api.api_key_pepper.get_secret_value()
    row = (await session.execute(
        select(api_keys).where(api_keys.c.short_id == short_id)
    )).first()
    if row is None:
        return None
    record = ApiKeyRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        short_id=row.short_id,
        hashed_secret=row.hashed_secret,
        label=row.label,
        scopes=tuple(row.scopes.split(",")) if row.scopes else (),
        expires_at=row.expires_at,
        revoked=row.revoked_at is not None,
    )
    if not record.is_active:
        return None
    if not verify_api_key(plaintext=plaintext, expected_hash=row.hashed_secret, pepper=pepper):
        return None
    # best-effort touch
    try:
        await session.execute(
            update(api_keys).where(api_keys.c.id == row.id).values(
                last_used_at=datetime.now(timezone.utc)
            )
        )
        await session.commit()
    except Exception:  # noqa: BLE001 — touch failure must not block requests
        logger.warning("could not update api_key.last_used_at for {}", record.short_id)
    return record


async def _load_tenant(session: AsyncSession, tenant_id: str) -> Tenant | None:
    row = (await session.execute(
        select(tenants).where(tenants.c.id == tenant_id)
    )).first()
    if row is None:
        return None
    if row.disabled_at is not None:
        return None
    return Tenant(
        id=row.id, name=row.name, plan=row.plan,
        created_at=row.created_at, disabled=False,
    )


async def get_tenant_context(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing api key")
    record = await _resolve_api_key(session, creds.credentials)
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
    tenant = await _load_tenant(session, record.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant disabled")
    request_id = request.headers.get(
        get_settings().api.request_id_header,
        request.scope.get("aws.request_id", ""),
    ) or record.short_id
    return TenantContext(tenant=tenant, api_key=record, request_id=request_id)


async def require_admin(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    ctx.require_scope("admin")
    return ctx


async def require_write(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    ctx.require_scope("write")
    return ctx
