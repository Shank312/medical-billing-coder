"""User and membership schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    organization_id: str
    role: str
    is_active: bool


class UserWithRole(BaseModel):
    user: UserOut
    role: str


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
