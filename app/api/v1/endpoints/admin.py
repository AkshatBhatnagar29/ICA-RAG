from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.auth import Role, TenantMembership, User
from app.schemas.admin import (
    CreateUserRequest,
    MembershipRequest,
    MembershipResponse,
    SetUserActiveRequest,
    UserResponse,
)
from app.security.auth import REQUIRE_ADMIN_USERS, AuthContext, hash_password

router = APIRouter(prefix="/admin", tags=["administration"])
DB_SESSION = Depends(get_db_session)


@router.get("/users", include_in_schema=False)
async def admin_users_page() -> RedirectResponse:
    """Keep the prototype's old browser link pointed at the SSR admin screen."""
    return RedirectResponse("/api/v1/ui/admin", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


async def _membership(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantMembership:
    result = await session.execute(select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user_id))
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Tenant membership was not found")
    return membership


async def _assert_not_final_admin(session: AsyncSession, tenant_id: uuid.UUID,
                                  membership: TenantMembership) -> None:
    if membership.role != Role.ADMIN:
        return
    count = await session.scalar(select(func.count()).select_from(TenantMembership).where(
        TenantMembership.tenant_id == tenant_id, TenantMembership.role == Role.ADMIN,
        TenantMembership.user_id != membership.user_id))
    if not count:
        raise HTTPException(status_code=409, detail="Tenant must retain an administrator")


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, context: AuthContext = REQUIRE_ADMIN_USERS,
                      session: AsyncSession = DB_SESSION) -> UserResponse:
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    session.add(user)
    try:
        await session.flush()
        membership = TenantMembership(tenant_id=context.tenant.id, user_id=user.id, role=payload.role)
        session.add(membership)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="User already exists") from exc
    return UserResponse(user_id=user.id, email=user.email, is_active=user.is_active,
                        tenant_id=context.tenant.id, role=payload.role)


@router.patch("/users/{user_id}/active", response_model=UserResponse)
async def set_user_active(user_id: uuid.UUID, payload: SetUserActiveRequest,
                          context: AuthContext = REQUIRE_ADMIN_USERS,
                          session: AsyncSession = DB_SESSION) -> UserResponse:
    membership = await _membership(session, context.tenant.id, user_id)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User was not found")
    if not payload.is_active:
        await _assert_not_final_admin(session, context.tenant.id, membership)
    user.is_active = payload.is_active
    await session.commit()
    return UserResponse(user_id=user.id, email=user.email, is_active=user.is_active,
                        tenant_id=context.tenant.id, role=membership.role)


@router.post("/memberships", response_model=MembershipResponse)
async def create_membership(payload: MembershipRequest, context: AuthContext = REQUIRE_ADMIN_USERS,
                            session: AsyncSession = DB_SESSION) -> MembershipResponse:
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User was not found")
    existing = await session.execute(select(TenantMembership).where(
        TenantMembership.tenant_id == context.tenant.id, TenantMembership.user_id == payload.user_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Tenant membership already exists")
    membership = TenantMembership(tenant_id=context.tenant.id, user_id=user.id, role=payload.role)
    session.add(membership)
    await session.commit()
    return MembershipResponse(user_id=user.id, tenant_id=context.tenant.id, role=membership.role)


@router.patch("/memberships/{user_id}/role", response_model=MembershipResponse)
async def change_membership_role(user_id: uuid.UUID, payload: MembershipRequest,
                                 context: AuthContext = REQUIRE_ADMIN_USERS,
                                 session: AsyncSession = DB_SESSION) -> MembershipResponse:
    if payload.user_id != user_id:
        raise HTTPException(status_code=422, detail="Resource ID does not match payload")
    membership = await _membership(session, context.tenant.id, user_id)
    if payload.role != Role.ADMIN:
        await _assert_not_final_admin(session, context.tenant.id, membership)
    membership.role = payload.role
    await session.commit()
    return MembershipResponse(user_id=user_id, tenant_id=context.tenant.id, role=membership.role)
