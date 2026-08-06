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
