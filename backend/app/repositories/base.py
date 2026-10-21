"""Repository base classes."""
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError


class BaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db


class TenantScopedRepository(BaseRepository):
    """Repository for resources owned by a single organization (tenant).

    ``organization_id`` is derived from the authenticated context, never from the
    client. Scoped lookups raise ``NotFoundError`` (404) for cross-tenant access so
    the existence of another tenant's resources is never leaked.
    """

    def __init__(self, db: Session, organization_id: str) -> None:
        super().__init__(db)
        self.organization_id = organization_id

    def require_tenant_match(self, resource_organization_id: str | None) -> None:
        if resource_organization_id != self.organization_id:
            raise NotFoundError("Resource not found")
