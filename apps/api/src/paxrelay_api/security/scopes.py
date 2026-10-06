"""API-key scope parsing and route authorization helpers."""

from __future__ import annotations

SCOPE_RESOURCES = frozenset(
    {
        "agents",
        "providers",
        "services",
        "policies",
        "approvals",
        "api-keys",
        "receipts",
        "transactions",
        "settlements",
        "analytics",
        "audit-logs",
        "webhooks",
        "batch",
        "project-members",
    }
)
SCOPE_ACTIONS = frozenset({"read", "write"})
ALL_SCOPES = frozenset(
    f"{resource}:{action}"
    for resource in SCOPE_RESOURCES
    for action in SCOPE_ACTIONS
) | frozenset({"gateway:invoke"})

ROLE_SCOPES: dict[str, frozenset[str]] = {
    "owner": ALL_SCOPES,
    "admin": ALL_SCOPES - {"gateway:invoke"},
    "operator": frozenset(
        {
            "agents:read", "agents:write", "providers:read", "providers:write",
            "services:read", "services:write", "policies:read", "policies:write",
            "approvals:read", "approvals:write", "receipts:read", "transactions:read",
            "settlements:read", "analytics:read", "audit-logs:read", "webhooks:read",
            "project-members:read",
        }
    ),
    "analyst": frozenset(
        {
            "agents:read", "providers:read", "services:read", "policies:read",
            "approvals:read", "approvals:write", "receipts:read", "transactions:read",
            "settlements:read", "analytics:read", "audit-logs:read", "project-members:read",
        }
    ),
    "viewer": frozenset(
        {
            "agents:read", "providers:read", "services:read", "policies:read",
            "approvals:read", "receipts:read", "transactions:read", "settlements:read",
            "analytics:read", "audit-logs:read",
        }
    ),
}


def parse_scopes(value: str | None) -> frozenset[str]:
    """Parse the persisted colon-paired representation into grants.

    Example: ``agents:read:agents:write`` becomes
    ``{"agents:read", "agents:write"}``. Unknown resources and malformed
    pairs fail closed so a bad stored value cannot accidentally grant access.
    """
    if not value:
        return frozenset()

    parts = value.split(":")
    if len(parts) % 2:
        raise ValueError("Scopes must contain resource/action pairs.")

    grants = frozenset(f"{resource}:{action}" for resource, action in zip(parts[::2], parts[1::2]))
    if not grants.issubset(ALL_SCOPES):
        raise ValueError("Scopes contain an unknown resource or action.")
    return grants


def encode_scopes(grants: frozenset[str] | set[str]) -> str:
    """Encode validated grants for the existing database string column."""
    if not grants.issubset(ALL_SCOPES):
        raise ValueError("Cannot encode unknown API-key scopes.")
    return ":".join(
        part
        for grant in sorted(grants)
        for part in grant.split(":", maxsplit=1)
    )
