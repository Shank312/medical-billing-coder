"""MFA schemas."""
from pydantic import BaseModel, Field


class MfaEnrollResponse(BaseModel):
    # Shown exactly once for QR provisioning; never logged or persisted in plaintext.
    secret: str
    otpauth_uri: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)


class MfaDisableRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=6, max_length=8)
