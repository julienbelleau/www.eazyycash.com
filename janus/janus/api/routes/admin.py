"""Admin-scope endpoints — tenant + API key management.

Restricted to keys with `admin` scope (typically the bootstrap key minted
by `scripts/admin_keys.py` at first deploy).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from janus.api.auth import TenantContext, require_admin
from janus.api.db import get_session
from janus.config.settings import get_settings
from janus.data.loaders.base import new_job_id
from janus.saas.tenant import (
    api_keys,
    generate_api_key,
    tenants,
)


router = APIRouter(prefix="/v1/admin", tags=["admin"])


# ─── tenants ───

class TenantCreate(BaseModel):
    name: str
    plan: str = "free"


class TenantView(BaseModel):
    id: str
    name: str
    plan: str
    created_at: datetime
    disabled: bool


@router.post("/tenants", response_model=TenantView, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    _ctx: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> TenantView:
    tid = new_job_id()
    now = datetime.now(timezone.utc)
    await session.execute(insert(tenants).values(
        id=tid, name=body.name, plan=body.plan, created_at=now,
    ))
    await session.commit()
    return TenantView(id=tid, name=body.name, plan=body.plan, created_at=now, disabled=False)


@router.get("/tenants", response_model=list[TenantView])
async def list_tenants(
    _ctx: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[TenantView]:
    rows = (await session.execute(select(tenants))).all()
    return [
        TenantView(
            id=r.id, name=r.name, plan=r.plan,
            created_at=r.created_at, disabled=r.disabled_at is not None,
        )
        for r in rows
    ]


# ─── api keys ───

class ApiKeyCreate(BaseModel):
    tenant_id: str
    label: str = ""
    scopes: list[str] = ["read"]


class ApiKeyCreated(BaseModel):
    id: str
    short_id: str
    plaintext: str   # ONLY returned at creation
    scopes: list[str]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    _ctx: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreated:
    pepper = get_settings().api.api_key_pepper.get_secret_value()
    gen = generate_api_key(pepper)
    key_id = new_job_id()
    await session.execute(insert(api_keys).values(
        id=key_id, tenant_id=body.tenant_id, short_id=gen.short_id,
        hashed_secret=gen.hashed_secret, label=body.label,
        scopes=",".join(body.scopes),
        created_at=datetime.now(timezone.utc),
    ))
    await session.commit()
    return ApiKeyCreated(
        id=key_id, short_id=gen.short_id, plaintext=gen.plaintext, scopes=body.scopes,
    )


@router.delete("/api-keys/{short_id}")
async def revoke_api_key(
    short_id: str,
    _ctx: TenantContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    result = await session.execute(
        update(api_keys).where(api_keys.c.short_id == short_id).values(
            revoked_at=datetime.now(timezone.utc)
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="key not found")
    await session.commit()
    return {"short_id": short_id, "status": "revoked"}
