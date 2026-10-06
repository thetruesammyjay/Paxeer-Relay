"""TenantContext — the per-request tenant identity every handler is scoped to.

Kept in its own module so it can be imported by both the security layer and
the dependencies module without creating a circular import.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant for the current request.

    Populated by the auth dependency from the verified API key's
    organisation/project columns.  Every DB query must filter by these values.
    """

    organisation_id: UUID
    project_id: UUID
    environment: str = "development"
    scopes: frozenset[str] = frozenset()
    api_key_id: UUID | None = None
    user_id: UUID | None = None
    membership_id: UUID | None = None
    role: str | None = None


def tenant_owns(tenant: TenantContext, resource: object) -> bool:
    """Return whether a resource belongs to this exact tenant and environment."""
    organisation_id = getattr(resource, "organisation_id", None)
    project_id = getattr(resource, "project_id", None)
    environment = getattr(resource, "environment", None)
    if hasattr(environment, "value"):
        environment = environment.value
    return (
        str(organisation_id) == str(tenant.organisation_id)
        and str(project_id) == str(tenant.project_id)
        and str(environment) == tenant.environment
    )
