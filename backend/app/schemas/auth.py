"""Authentication schemas."""
from pydantic import BaseModel, EmailStr, Field

from .organization import OrganizationOut
from .user import UserOut


class RegisterRequest(BaseModel):
    organization_name: str = Field(..., min_length=1, max_length=255)
    organization_slug: str | None = Field(default=None, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    organization_id: str | None = None
    mfa_code: str | None = Field(default=None, max_length=16)


class RefreshRequest(BaseModel):
    # Optional: the refresh token may instead arrive as an HttpOnly cookie.
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    user: UserOut
    organization: OrganizationOut


class MeResponse(BaseModel):
    user: UserOut
    organization: OrganizationOut
    roles: list[str]
