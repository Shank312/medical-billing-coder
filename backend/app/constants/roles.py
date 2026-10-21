"""Role definitions and authorization groupings.

Roles are tenant-scoped: a user holds a role through a ``membership`` in an
organization. Authorization is deny-by-default; an endpoint must explicitly
list the roles it permits.
"""
from enum import Enum


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    PROVIDER = "provider"
    CODER = "coder"
    BILLER = "biller"
    AUDITOR = "auditor"
    READ_ONLY = "read_only"


ALL_ROLES: tuple[Role, ...] = tuple(Role)

# Roles permitted to mutate organization-scoped data in Phase 1.
MUTATING_ROLES: tuple[Role, ...] = (Role.OWNER, Role.ADMIN)

# Roles reserved for the organization owner.
OWNER_ROLES: tuple[Role, ...] = (Role.OWNER,)

# Roles granted read access to organization-scoped data in Phase 1.
READ_ROLES: tuple[Role, ...] = ALL_ROLES


def is_valid_role(role: str) -> bool:
    """Return True when ``role`` is a known role name."""
    return role in {r.value for r in Role}


def role_priority(role: str) -> int:
    """Return an ordering value for a role; lower is more privileged."""
    order: dict[str, int] = {
        Role.OWNER.value: 0,
        Role.ADMIN.value: 1,
        Role.PROVIDER.value: 2,
        Role.CODER.value: 3,
        Role.BILLER.value: 4,
        Role.AUDITOR.value: 5,
        Role.READ_ONLY.value: 6,
    }
    return order.get(role, 99)
