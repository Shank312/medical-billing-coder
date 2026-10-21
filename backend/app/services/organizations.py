"""Organization and membership business logic (tenant-scoped)."""
from sqlalchemy.orm import Session

from ..constants.roles import Role, is_valid_role
from ..core.errors import BadRequestError, ConflictError, NotFoundError
from ..models.membership import Membership
from ..models.organization import Organization
from ..models.user import User
from ..repositories.memberships import MembershipRepository
from ..repositories.organizations import OrganizationRepository
from ..repositories.users import UserRepository
from .audit import AuditService


def get_organization(db: Session, organization_id: str) -> Organization:
    organization = OrganizationRepository(db).get(organization_id)
    if organization is None:
        raise NotFoundError("Organization not found")
    return organization


def update_organization(
    db: Session,
    *,
    organization_id: str,
    name: str | None,
    slug: str | None,
    actor_user_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Organization:
    org_repo = OrganizationRepository(db)
    organization = get_organization(db, organization_id)

    if name is not None:
        organization.name = name
    if slug is not None:
        new_slug = slug.lower().strip()
        existing = org_repo.get_by_slug(new_slug)
        if existing is not None and existing.id != organization_id:
            raise ConflictError("Organization slug already in use", code="slug_in_use")
        organization.slug = new_slug

    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="organization.updated",
        resource_type="organization",
        resource_id=organization_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"name": organization.name, "slug": organization.slug},
    )
    return organization


def list_members(db: Session, organization_id: str) -> list[tuple[User, Membership]]:
    return MembershipRepository(db, organization_id).list_members()


def add_member(
    db: Session,
    *,
    organization_id: str,
    email: str,
    full_name: str,
    role: str,
    actor_user_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, Membership]:
    if not is_valid_role(role):
        raise BadRequestError("Invalid role", code="invalid_role")

    get_organization(db, organization_id)
    membership_repo = MembershipRepository(db, organization_id)

    email_norm = email.lower().strip()
    user = UserRepository(db).get_by_email(email_norm)
    if user is None:
        # Provisional invite record: an unactivated account with no password.
        # A dedicated invitation/claim flow lands in a later phase.
        user = UserRepository(db).create(
            email=email_norm, full_name=full_name, password_hash="", is_active=False
        )

    if membership_repo.get_by_user(user.id) is not None:
        raise ConflictError("User is already a member of this organization", code="already_member")

    membership = membership_repo.create(user_id=user.id, role=role)
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="membership.created",
        resource_type="membership",
        resource_id=membership.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"user_id": user.id, "role": role},
    )
    return user, membership


def update_member(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    role: str | None,
    is_active: bool | None,
    actor_user_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, Membership]:
    if role is not None and not is_valid_role(role):
        raise BadRequestError("Invalid role", code="invalid_role")

    membership_repo = MembershipRepository(db, organization_id)
    user, membership = membership_repo.get_member(user_id)

    if membership.role == Role.OWNER.value:
        if role is not None and role != Role.OWNER.value:
            if membership_repo.count_active_owners() <= 1:
                raise ConflictError("Cannot change the role of the last owner", code="last_owner")
        if is_active is False:
            raise ConflictError("Cannot deactivate the last owner", code="last_owner")

    if role is not None:
        membership.role = role
    if is_active is not None:
        membership.is_active = is_active

    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="membership.updated",
        resource_type="membership",
        resource_id=membership.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"user_id": user_id, "role": membership.role, "is_active": membership.is_active},
    )
    return user, membership


def remove_member(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    actor_user_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    membership_repo = MembershipRepository(db, organization_id)
    _user, membership = membership_repo.get_member(user_id)

    if membership.role == Role.OWNER.value and membership_repo.count_active_owners() <= 1:
        raise ConflictError("Cannot remove the last owner", code="last_owner")

    db.delete(membership)
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="membership.removed",
        resource_type="membership",
        resource_id=membership.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"user_id": user_id},
    )
