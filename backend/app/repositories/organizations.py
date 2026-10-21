"""Organization repository."""
from sqlalchemy import select

from ..models.organization import Organization
from .base import BaseRepository


class OrganizationRepository(BaseRepository):
    def get(self, organization_id: str) -> Organization | None:
        return self.db.get(Organization, organization_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.db.execute(
            select(Organization).where(Organization.slug == slug)
        ).scalar_one_or_none()

    def create(self, *, name: str, slug: str) -> Organization:
        organization = Organization(name=name, slug=slug)
        self.db.add(organization)
        self.db.flush()
        return organization
