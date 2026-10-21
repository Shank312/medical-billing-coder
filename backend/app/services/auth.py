"""Authentication and session business logic.

Refresh tokens are stored as SHA-256 hashes and rotated on every use; reuse of a
rotated token revokes all of the user's sessions in that organization.
"""
import re
from datetime import timedelta

from sqlalchemy.orm import Session

from ..constants.roles import Role
from ..core import security
from ..core.config import get_settings
from ..core.time import utcnow
from ..core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from ..models.membership import Membership
from ..models.organization import Organization
from ..models.refresh_token import RefreshToken
from ..models.user import User
from ..repositories.memberships import list_memberships_for_user
from ..repositories.organizations import OrganizationRepository
from ..repositories.refresh_tokens import RefreshTokenRepository
from ..repositories.users import UserRepository
from .audit import AuditService
from .mfa import mfa_enabled, verify_totp


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "org"


def _issue_tokens(
    db: Session,
    user: User,
    organization: Organization,
    roles: list[str],
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, int, RefreshToken]:
    settings = get_settings()
    access_token = security.create_access_token(
        user_id=user.id, organization_id=organization.id, roles=roles
    )
    expires_in = settings.access_token_expire_minutes * 60
    raw_refresh = security.generate_refresh_token()
    refresh_row = RefreshTokenRepository(db).create(
        user_id=user.id,
        organization_id=organization.id,
        token_hash=security.hash_refresh_token(raw_refresh),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return access_token, raw_refresh, expires_in, refresh_row


def _audit_failed_login(
    db: Session,
    email: str,
    user_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    AuditService.append(
        db,
        organization_id=None,
        actor_user_id=user_id,
        action="auth.login_failed",
        resource_type="user",
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"email": email},
    )


def register(
    db: Session,
    *,
    organization_name: str,
    organization_slug: str | None,
    full_name: str,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[Organization, User, str, str, int]:
    email_norm = email.lower().strip()
    if UserRepository(db).get_by_email(email_norm) is not None:
        raise ConflictError("An account with this email already exists", code="email_in_use")

    slug = (organization_slug or _slugify(organization_name)).lower().strip()
    org_repo = OrganizationRepository(db)
    if org_repo.get_by_slug(slug) is not None:
        raise ConflictError("Organization slug already in use", code="slug_in_use")

    organization = org_repo.create(name=organization_name, slug=slug)
    user = UserRepository(db).create(
        email=email_norm, full_name=full_name, password_hash=security.hash_password(password)
    )
    membership = Membership(
        user_id=user.id, organization_id=organization.id, role=Role.OWNER.value
    )
    db.add(membership)
    db.flush()

    access_token, raw_refresh, expires_in, _row = _issue_tokens(
        db, user, organization, [Role.OWNER.value], ip_address=ip_address, user_agent=user_agent
    )

    AuditService.append(
        db,
        organization_id=organization.id,
        actor_user_id=user.id,
        action="organization.created",
        resource_type="organization",
        resource_id=organization.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"name": organization.name, "slug": organization.slug},
    )
    AuditService.append(
        db,
        organization_id=organization.id,
        actor_user_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={"email": email_norm},
    )
    return organization, user, access_token, raw_refresh, expires_in


def login(
    db: Session,
    *,
    email: str,
    password: str,
    organization_id: str | None = None,
    mfa_code: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[Organization, User, list[str], str, str, int]:
    email_norm = email.lower().strip()
    user = UserRepository(db).get_by_email(email_norm)
    if user is None or not user.is_active:
        _audit_failed_login(db, email_norm, user.id if user else None, ip_address, user_agent)
        raise UnauthorizedError("Invalid email or password")

    if not security.verify_password(password, user.password_hash):
        _audit_failed_login(db, email_norm, user.id, ip_address, user_agent)
        raise UnauthorizedError("Invalid email or password")

    memberships = [m for m in list_memberships_for_user(db, user.id) if m.is_active]
    if not memberships:
        raise ForbiddenError("No active organization membership")

    membership = _resolve_membership(memberships, organization_id)
    if membership is None and organization_id is not None:
        _audit_failed_login(db, email_norm, user.id, ip_address, user_agent)
        raise ForbiddenError("Not a member of the requested organization")
    if membership is None:
        raise BadRequestError(
            "organization_id is required for multi-organization accounts",
            code="organization_required",
        )

    organization = OrganizationRepository(db).get(membership.organization_id)
    if organization is None or not organization.is_active:
        raise ForbiddenError("Organization is inactive")

    if mfa_enabled(db, user.id):
        if not mfa_code:
            raise UnauthorizedError("MFA code required", code="mfa_required")
        if not verify_totp(db, user.id, mfa_code):
            _audit_failed_login(db, email_norm, user.id, ip_address, user_agent)
            raise UnauthorizedError("Invalid MFA code")

    roles = [membership.role]
    access_token, raw_refresh, expires_in, _row = _issue_tokens(
        db, user, organization, roles, ip_address=ip_address, user_agent=user_agent
    )
    AuditService.append(
        db,
        organization_id=organization.id,
        actor_user_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return organization, user, roles, access_token, raw_refresh, expires_in


def _resolve_membership(
    memberships: list[Membership], organization_id: str | None
) -> Membership | None:
    if organization_id is not None:
        return next((m for m in memberships if m.organization_id == organization_id), None)
    return memberships[0] if len(memberships) == 1 else None


def refresh(
    db: Session,
    *,
    refresh_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[Organization, User, list[str], str, str, int]:
    if not refresh_token:
        raise UnauthorizedError("Refresh token required")

    token_hash = security.hash_refresh_token(refresh_token)
    repo = RefreshTokenRepository(db)
    stored = repo.get_by_hash(token_hash)
    if stored is None:
        raise UnauthorizedError("Invalid refresh token")

    now = utcnow()

    if stored.revoked_at is not None:
        # Reuse of a rotated/revoked token: revoke the whole session family.
        repo.revoke_all_for_user_org(stored.user_id, stored.organization_id, now)
        AuditService.append(
            db,
            organization_id=stored.organization_id,
            actor_user_id=stored.user_id,
            action="auth.refresh_reuse_detected",
            resource_type="refresh_token",
            resource_id=stored.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise UnauthorizedError(
            "Refresh token reuse detected; sessions revoked", code="refresh_reuse"
        )

    if stored.expires_at < now:
        stored.revoked_at = now
        AuditService.append(
            db,
            organization_id=stored.organization_id,
            actor_user_id=stored.user_id,
            action="auth.refresh_expired",
            resource_type="refresh_token",
            resource_id=stored.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise UnauthorizedError("Refresh token expired")

    user = UserRepository(db).get(stored.user_id)
    organization = OrganizationRepository(db).get(stored.organization_id)
    if user is None or not user.is_active or organization is None or not organization.is_active:
        raise UnauthorizedError("Session no longer valid")

    membership = next(
        (
            m
            for m in list_memberships_for_user(db, user.id)
            if m.organization_id == organization.id and m.is_active
        ),
        None,
    )
    if membership is None:
        raise UnauthorizedError("Session no longer valid")

    # Rotate: revoke the presented token and issue a fresh one.
    stored.revoked_at = now
    access_token, raw_refresh, expires_in, new_row = _issue_tokens(
        db, user, organization, [membership.role], ip_address=ip_address, user_agent=user_agent
    )
    stored.replaced_by_id = new_row.id
    AuditService.append(
        db,
        organization_id=organization.id,
        actor_user_id=user.id,
        action="auth.refresh",
        resource_type="refresh_token",
        resource_id=new_row.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return organization, user, [membership.role], access_token, raw_refresh, expires_in


def logout(
    db: Session,
    *,
    refresh_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    if not refresh_token:
        raise UnauthorizedError("Refresh token required")

    stored = RefreshTokenRepository(db).get_by_hash(security.hash_refresh_token(refresh_token))
    if stored is None:
        return  # idempotent

    if stored.revoked_at is None:
        stored.revoked_at = utcnow()
    AuditService.append(
        db,
        organization_id=stored.organization_id,
        actor_user_id=stored.user_id,
        action="auth.logout",
        resource_type="refresh_token",
        resource_id=stored.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def revoke_all_sessions(
    db: Session,
    *,
    user_id: str,
    organization_id: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    RefreshTokenRepository(db).revoke_all_for_user_org(user_id, organization_id, utcnow())
    AuditService.append(
        db,
        organization_id=organization_id,
        actor_user_id=user_id,
        action="auth.sessions_revoked",
        resource_type="user",
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
