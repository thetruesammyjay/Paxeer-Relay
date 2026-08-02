"""Shared mapping helpers for translating between ORM rows and domain models.

The domain layer uses ``uuid.UUID`` and ``MonetaryAmount`` value objects, while
the ORM stores UUIDs as strings and money as separate atomic/currency/decimals
columns. These helpers keep that translation in one place.
"""

from __future__ import annotations

from uuid import UUID

from paxrelay_domain import Currency, MonetaryAmount


def as_uuid(value: str | UUID) -> UUID:
    """Coerce a stored string (or UUID) into a ``uuid.UUID``."""
    return value if isinstance(value, UUID) else UUID(str(value))


def sid(value: str | UUID) -> str:
    """Render a UUID (or string) as the string form the ORM stores."""
    return str(value)


def money(amount_atomic: int, currency: str, decimals: int) -> MonetaryAmount:
    """Rebuild a :class:`MonetaryAmount` from its persisted columns."""
    return MonetaryAmount(
        amount_atomic=int(amount_atomic),
        currency=Currency(currency),
        decimals=decimals,
    )
