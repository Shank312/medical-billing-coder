"""Organization schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=100)


class AddUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=50)
