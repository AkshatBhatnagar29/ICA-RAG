"""Idempotently seed development-only auth data for integration tests.

This script never runs from application startup and never prints credentials.
Override the deterministic test password with ICIA_TEST_PASSWORD when needed.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.models.auth import Role, Tenant, TenantMembership, User
from app.security.auth import hash_password

NAMESPACE = uuid.UUID("9c9e4b9e-3ca0-4b7a-9b55-4b2c2dfac1e1")
TEST_PASSWORD = os.getenv("ICIA_TEST_PASSWORD", "phase12-development-only-password")
USERS = (
    ("tenant-a", "Tenant A", "admin-a@example.test", Role.ADMIN),
    ("tenant-a", "Tenant A", "reviewer-a@example.test", Role.REVIEWER),
    ("tenant-a", "Tenant A", "viewer-a@example.test", Role.VIEWER),
    ("tenant-b", "Tenant B", "admin-b@example.test", Role.ADMIN),
)


async def seed() -> None:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise RuntimeError("auth test seed is permitted only in development or test environments")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        tenants: dict[str, Tenant] = {}
        for identifier, name, _, _ in USERS:
            tenant = (await session.execute(select(Tenant).where(Tenant.identifier == identifier))).scalar_one_or_none()
            if tenant is None:
                tenant = Tenant(id=uuid.uuid5(NAMESPACE, f"tenant:{identifier}"), identifier=identifier, name=name)
                session.add(tenant)
                await session.flush()
            tenants[identifier] = tenant
        for identifier, _, email, role in USERS:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                user = User(id=uuid.uuid5(NAMESPACE, f"user:{email}"), email=email,
                            password_hash=hash_password(TEST_PASSWORD), is_active=True)
                session.add(user)
                await session.flush()
            membership = (await session.execute(select(TenantMembership).where(
                TenantMembership.tenant_id == tenants[identifier].id, TenantMembership.user_id == user.id
            ))).scalar_one_or_none()
            if membership is None:
                session.add(TenantMembership(id=uuid.uuid5(NAMESPACE, f"membership:{identifier}:{email}"),
                                              tenant_id=tenants[identifier].id, user_id=user.id, role=role))
            elif membership.role != role:
                membership.role = role
        await session.commit()
    await engine.dispose()
    print("Development auth test data is ready.")


if __name__ == "__main__":
    asyncio.run(seed(), loop_factory=asyncio.SelectorEventLoop)
