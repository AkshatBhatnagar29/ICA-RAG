from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.auth import Role


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    role: Role = Role.VIEWER


class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    is_active: bool
    tenant_id: uuid.UUID
    role: Role


class SetUserActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class MembershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID
    role: Role


class MembershipResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role
