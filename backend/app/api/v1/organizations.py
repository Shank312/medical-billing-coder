"""Organization and membership endpoints (tenant-scoped, RBAC-enforced)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...constants.roles import Role
from ...core.errors import NotFoundError
from ...db.session import get_db_session
from ...schemas.common import MessageResponse
from ...schemas.organization import AddUserRequest, OrganizationOut, OrganizationUpdate
from ...schemas.user import UserOut, UserUpdate, UserWithRole
from ..deps import AuthContext, get_auth_context, request_info, require_roles

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _require_tenant(auth: AuthContext, organization_id: str) -> None:
    """Enforce tenant isolation: the path org id must match the token's org id."""
    if organization_id != auth.organization_id:
        raise NotFoundError("Organization not found")


@router.get("/{organization_id}", response_model=OrganizationOut)
def get_organization(
    organization_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    _require_tenant(auth, organization_id)
    from ...services import organizations as org_service

    return OrganizationOut.model_validate(org_service.get_organization(db, organization_id))


@router.patch("/{organization_id}", response_model=OrganizationOut)
def update_organization(
    organization_id: str,
    body: OrganizationUpdate,
    request: Request,
    auth: AuthContext = Depends(require_roles(Role.OWNER, Role.ADMIN)),
    db: Session = Depends(get_db_session),
):
    _require_tenant(auth, organization_id)
    ip, ua = request_info(request)
    from ...services import organizations as org_service

    try:
        organization = org_service.update_organization(
            db,
            organization_id=organization_id,
            name=body.name,
            slug=body.slug,
            actor_user_id=auth.user_id,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return OrganizationOut.model_validate(organization)


@router.get("/{organization_id}/users", response_model=list[UserWithRole])
def list_users(
    organization_id: str,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    _require_tenant(auth, organization_id)
    from ...services import organizations as org_service

    members = org_service.list_members(db, organization_id)
    return [UserWithRole(user=UserOut.model_validate(u), role=m.role) for u, m in members]


@router.post("/{organization_id}/users", response_model=UserWithRole, status_code=201)
def add_user(
    organization_id: str,
    body: AddUserRequest,
    request: Request,
    auth: AuthContext = Depends(require_roles(Role.OWNER, Role.ADMIN)),
    db: Session = Depends(get_db_session),
):
    _require_tenant(auth, organization_id)
    ip, ua = request_info(request)
    from ...services import organizations as org_service

    try:
        user, membership = org_service.add_member(
            db,
            organization_id=organization_id,
            email=body.email,
            full_name=body.full_name,
            role=body.role,
            actor_user_id=auth.user_id,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return UserWithRole(user=UserOut.model_validate(user), role=membership.role)


@router.patch("/{organization_id}/users/{user_id}", response_model=UserWithRole)
def update_user(
    organization_id: str,
    user_id: str,
    body: UserUpdate,
    request: Request,
    auth: AuthContext = Depends(require_roles(Role.OWNER, Role.ADMIN)),
    db: Session = Depends(get_db_session),
):
    _require_tenant(auth, organization_id)
    ip, ua = request_info(request)
    from ...services import organizations as org_service

    try:
        user, membership = org_service.update_member(
            db,
            organization_id=organization_id,
            user_id=user_id,
            role=body.role,
            is_active=body.is_active,
            actor_user_id=auth.user_id,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return UserWithRole(user=UserOut.model_validate(user), role=membership.role)


@router.delete("/{organization_id}/users/{user_id}", response_model=MessageResponse)
def remove_user(
    organization_id: str,
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(require_roles(Role.OWNER, Role.ADMIN)),
    db: Session = Depends(get_db_session),
):
    _require_tenant(auth, organization_id)
    ip, ua = request_info(request)
    from ...services import organizations as org_service

    try:
        org_service.remove_member(
            db,
            organization_id=organization_id,
            user_id=user_id,
            actor_user_id=auth.user_id,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return MessageResponse(message="Member removed")
