from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, cast

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.auth import Role, Tenant, TenantMembership, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
DB_SESSION = Depends(get_db_session)


class Permission(StrEnum):
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    SEARCH_READ = "search:read"
    CONTRACTS_READ = "contracts:read"
    CONTRACTS_ANALYZE = "contracts:analyze"
    CONTRACTS_COMPARE = "contracts:compare"
    LEGAL_READ = "legal:read"
    AGENT_USE = "agent:use"
    ADMIN_MANAGE_USERS = "admin:manage_users"
    ADMIN_MANAGE_TENANT = "admin:manage_tenant"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.REVIEWER: frozenset({Permission.DOCUMENTS_READ, Permission.DOCUMENTS_WRITE,
                              Permission.SEARCH_READ, Permission.CONTRACTS_READ,
                              Permission.CONTRACTS_ANALYZE, Permission.CONTRACTS_COMPARE,
                              Permission.LEGAL_READ, Permission.AGENT_USE}),
    Role.VIEWER: frozenset({Permission.DOCUMENTS_READ, Permission.SEARCH_READ,
                            Permission.CONTRACTS_READ, Permission.LEGAL_READ}),
}


@dataclass(frozen=True)
class AuthContext:
    user: User
    tenant: Tenant
    membership: TenantMembership


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, digest = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=2**14, r=8, p=1)
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    settings = get_settings()
    if not settings.auth_jwt_secret:
        raise RuntimeError("AUTH_JWT_SECRET must be configured")
    now = datetime.now(UTC)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(user_id), "tenant_id": str(tenant_id), "iat": int(now.timestamp()),
               "exp": int((now + timedelta(minutes=settings.auth_access_token_minutes)).timestamp()),
               "iss": settings.auth_issuer, "aud": settings.auth_audience, "typ": "access"}
    encoded = f"{_b64(json.dumps(header, separators=(",", ":")).encode())}.{_b64(json.dumps(payload, separators=(",", ":")).encode())}"
    return f"{encoded}.{_b64(hmac.new(settings.auth_jwt_secret.encode(), encoded.encode(), hashlib.sha256).digest())}"


def _claims(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        head, body, signature = token.split(".")
        expected = hmac.new(settings.auth_jwt_secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
        if not settings.auth_jwt_secret or not hmac.compare_digest(expected, _unb64(signature)):
            raise TypeError
        header = json.loads(_unb64(head)); claims = json.loads(_unb64(body))
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise TypeError
        if header.get("alg") != "HS256" or claims.get("typ") != "access":
            raise ValueError
        now = int(datetime.now(UTC).timestamp())
        if not isinstance(claims.get("sub"), str) or not isinstance(claims.get("tenant_id"), str) or int(claims["exp"]) <= now:
            raise ValueError
        if claims.get("iss") != settings.auth_issuer or claims.get("aud") != settings.auth_audience:
            raise ValueError
        return cast(dict[str, object], claims)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})


async def get_current_context(token: Annotated[str, Depends(oauth2_scheme)],
                              x_tenant_id: Annotated[uuid.UUID | None, Header()] = None,
                              session: AsyncSession = DB_SESSION) -> AuthContext:
    claims = _claims(token)
    try:
        user_id = uuid.UUID(str(claims["sub"])); token_tenant = uuid.UUID(str(claims["tenant_id"]))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    # The signed token is authoritative. A caller-controlled header may select
    # a tenant only when it matches the authenticated tenant exactly.
    if x_tenant_id is not None and x_tenant_id != token_tenant:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    tenant_id = token_tenant
    row = (await session.execute(select(User, Tenant, TenantMembership).join(TenantMembership, TenantMembership.user_id == User.id)
          .join(Tenant, Tenant.id == TenantMembership.tenant_id).where(User.id == user_id, User.is_active.is_(True), TenantMembership.tenant_id == tenant_id))).one_or_none()
    if row is None:
        raise HTTPException(status_code=403, detail="Tenant access denied")
    return AuthContext(user=row[0], tenant=row[1], membership=row[2])


def require_permission(permission: Permission) -> Callable[..., object]:
    async def dependency(context: Annotated[AuthContext, Depends(get_current_context)]) -> AuthContext:
        if permission not in ROLE_PERMISSIONS[context.membership.role]:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return context
    return dependency


REQUIRE_DOCUMENTS_WRITE = Depends(require_permission(Permission.DOCUMENTS_WRITE))
REQUIRE_SEARCH_READ = Depends(require_permission(Permission.SEARCH_READ))
REQUIRE_AGENT_USE = Depends(require_permission(Permission.AGENT_USE))
REQUIRE_CONTRACTS_READ = Depends(require_permission(Permission.CONTRACTS_READ))
REQUIRE_CONTRACTS_ANALYZE = Depends(require_permission(Permission.CONTRACTS_ANALYZE))
REQUIRE_CONTRACTS_COMPARE = Depends(require_permission(Permission.CONTRACTS_COMPARE))
REQUIRE_ADMIN_USERS = Depends(require_permission(Permission.ADMIN_MANAGE_USERS))
