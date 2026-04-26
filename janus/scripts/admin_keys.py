"""Admin CLI: bootstrap a tenant + first API key.

Runs out-of-band — meant for the human operator after the migrate service
has run on Railway. Outputs the plaintext API key ONCE; Janus never stores
it. Save it in your secret manager.

Examples:
    poetry run python scripts/admin_keys.py create-tenant --name acme --plan pro
    poetry run python scripts/admin_keys.py issue-key --tenant <id> --label primary --scopes admin
    poetry run python scripts/admin_keys.py revoke-key --short-id abcd1234
    poetry run python scripts/admin_keys.py list-tenants
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from janus.config.settings import get_settings
from janus.data.loaders.base import new_job_id
from janus.monitoring.logging_config import configure_logging
from janus.saas.tenant import api_keys, generate_api_key, tenants


async def _session_factory() -> async_sessionmaker:
    engine = create_async_engine(get_settings().database.async_dsn, future=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def cmd_create_tenant(args: argparse.Namespace) -> int:
    sf = await _session_factory()
    async with sf() as s:
        tid = new_job_id()
        await s.execute(insert(tenants).values(
            id=tid, name=args.name, plan=args.plan,
            created_at=datetime.now(timezone.utc),
        ))
        await s.commit()
    print(f"tenant_id={tid} name={args.name} plan={args.plan}")
    return 0


async def cmd_issue_key(args: argparse.Namespace) -> int:
    pepper = get_settings().api.api_key_pepper.get_secret_value()
    gen = generate_api_key(pepper)
    sf = await _session_factory()
    async with sf() as s:
        await s.execute(insert(api_keys).values(
            id=new_job_id(),
            tenant_id=args.tenant,
            short_id=gen.short_id,
            hashed_secret=gen.hashed_secret,
            label=args.label,
            scopes=args.scopes,
            created_at=datetime.now(timezone.utc),
        ))
        await s.commit()
    print("# Save this key — it will not be shown again:")
    print(gen.plaintext)
    print(f"# short_id={gen.short_id}  scopes={args.scopes}")
    return 0


async def cmd_revoke_key(args: argparse.Namespace) -> int:
    sf = await _session_factory()
    async with sf() as s:
        result = await s.execute(
            update(api_keys).where(api_keys.c.short_id == args.short_id).values(
                revoked_at=datetime.now(timezone.utc)
            )
        )
        await s.commit()
    print(f"revoked rows={result.rowcount}")
    return 0


async def cmd_list_tenants(args: argparse.Namespace) -> int:
    sf = await _session_factory()
    async with sf() as s:
        rows = (await s.execute(select(tenants))).all()
    for r in rows:
        print(f"{r.id}\t{r.name}\t{r.plan}\tdisabled_at={r.disabled_at}")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    ct = sub.add_parser("create-tenant")
    ct.add_argument("--name", required=True)
    ct.add_argument("--plan", default="free")

    ik = sub.add_parser("issue-key")
    ik.add_argument("--tenant", required=True)
    ik.add_argument("--label", default="")
    ik.add_argument("--scopes", default="read,write",
                     help="comma-separated. Use 'admin' for full access.")

    rk = sub.add_parser("revoke-key")
    rk.add_argument("--short-id", required=True)

    sub.add_parser("list-tenants")
    return p


async def _main() -> int:
    configure_logging()
    args = _parser().parse_args()
    if args.cmd == "create-tenant":
        return await cmd_create_tenant(args)
    if args.cmd == "issue-key":
        return await cmd_issue_key(args)
    if args.cmd == "revoke-key":
        return await cmd_revoke_key(args)
    if args.cmd == "list-tenants":
        return await cmd_list_tenants(args)
    return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
