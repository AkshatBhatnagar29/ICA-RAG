import uuid

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class BootstrapRequest(BaseModel):
    tenant_identifier: str = Field(min_length=1, max_length=128)
    tenant_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)

class BootstrapResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
