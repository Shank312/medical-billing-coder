"""Membership repository (tenant-scoped) plus a cross-org helper for login."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..constants.roles import Role
from ..core.errors import NotFoundError
from ..models.membership import Membership
from ..models.user import User
from .base import TenantScopedRepository


def list_memberships_for_user(db: Session, user_id: str) -> list[Membership]:
    """Return all memberships for a user across organizations (used at login)."""
    return db.execute(select(Membership).where(Membership.user_id == user_id)).scalars().all()


class MembershipRepository(TenantScopedRepository):
    def list_members(self) -> list[tuple[User, Membership]]:
        return self.db.execute(
            select(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == self.organization_id)
            .order_by(User.email)
        ).all()

    def get_member(self, user_id: str) -> tuple[User, Membership]:
        row = self.db.execute(
            select(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.organization_id == self.organization_id,
                Membership.user_id == user_id,
            )
        ).first()
        if row is None:
            raise NotFoundError("User not found in this organization")
        return row

    def get_by_user(self, user_id: str) -> Membership | None:
        return self.db.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.organization_id == self.organization_id,
            )
        ).scalar_one_or_none()

    def create(self, *, user_id: str, role: str) -> Membership:
        membership = Membership(
            user_id=user_id, organization_id=self.organization_id, role=role
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def count_active_owners(self) -> int:
        return len(
            self.db.execute(
                select(Membership).where(
                    Membership.organization_id == self.organization_id,
                    Membership.role == Role.OWNER.value,
                    Membership.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
