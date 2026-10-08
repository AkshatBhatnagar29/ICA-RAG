from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Role, Tenant, TenantMembership, User
from app.schemas.auth import BootstrapRequest, BootstrapResponse, TokenResponse
from app.security.auth import DB_SESSION, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=TokenResponse)
async def token(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()],
               session: AsyncSession = DB_SESSION) -> TokenResponse:
    user = (await session.execute(select(User).where(User.email == form.username.lower()))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password", headers={"WWW-Authenticate": "Bearer"})
    membership = (await session.execute(select(TenantMembership).where(TenantMembership.user_id == user.id))).scalars().first()
    if membership is None:
        raise HTTPException(status_code=403, detail="User has no tenant membership")
    return TokenResponse(access_token=create_access_token(user.id, membership.tenant_id))


@router.post("/bootstrap", response_model=BootstrapResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap(payload: BootstrapRequest, request: Request,
                    x_bootstrap_token: Annotated[str | None, Header()] = None,
                    session: AsyncSession = DB_SESSION) -> BootstrapResponse:
    settings = request.app.state.settings
    if settings.app_env.lower() not in {"development", "test"} or not settings.auth_bootstrap_token or not x_bootstrap_token or x_bootstrap_token != settings.auth_bootstrap_token:
        raise HTTPException(status_code=404, detail="Not found")
    if len(payload.password) < settings.auth_password_min_length:
        raise HTTPException(status_code=422, detail="Password does not meet the configured policy")
    if (await session.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists")
    if (await session.execute(select(Tenant).where(Tenant.identifier == payload.tenant_identifier))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tenant identifier already exists")
    tenant = Tenant(identifier=payload.tenant_identifier, name=payload.tenant_name)
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    session.add_all([tenant, user]); await session.flush()
    session.add(TenantMembership(tenant_id=tenant.id, user_id=user.id, role=Role.ADMIN))
    await session.commit()
    return BootstrapResponse(user_id=user.id, tenant_id=tenant.id)
