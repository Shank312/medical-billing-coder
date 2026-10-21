"""Shared API dependencies: authentication context and RBAC."""
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..constants.roles import Role
from ..core.errors import ForbiddenError, UnauthorizedError
from ..core.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user_id: str
    organization_id: str
    roles: list[str]


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    """Resolve the authenticated user and tenant from the Bearer access token."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Authentication required")
    payload = decode_access_token(credentials.credentials)
    return AuthContext(
        user_id=payload["sub"],
        organization_id=payload["org_id"],
        roles=list(payload["roles"]),
    )


def require_roles(*allowed: Role):
    """Deny-by-default authorization: only the listed roles pass.

    Usage: ``auth: AuthContext = Depends(require_roles(Role.OWNER, Role.ADMIN))``.
    """
    allowed_set = {role.value for role in allowed}

    def _dependency(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not (set(auth.roles) & allowed_set):
            raise ForbiddenError("Insufficient permissions for this action")
        return auth

    return _dependency


def request_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and user-agent for audit context (never log bodies)."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent
