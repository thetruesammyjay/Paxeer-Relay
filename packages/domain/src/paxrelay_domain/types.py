"""
Shared primitive types and value objects for the PaxRelay domain layer.

All types here are framework-independent — no FastAPI, SQLAlchemy, or
HTTP client imports are permitted in this module.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import Enum
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAXEER_CHAIN_ID: Final[int] = 125
USDX_DECIMALS: Final[int] = 6  # USDX uses 6 decimal places (like USDC)
EVM_ADDRESS_RE: Final[re.Pattern[str]] = re.compile(r"^0x[0-9a-fA-F]{40}$")

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Environment(str, Enum):
    """Deployment environment for tenant scoping."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Currency(str, Enum):
    """Supported payment currencies."""

    USDX = "USDX"


# ---------------------------------------------------------------------------
# Primitive value objects
# ---------------------------------------------------------------------------


def _validate_wallet_address(value: str) -> str:
    """Validate and normalise an EVM wallet address.

    Accepts 0x-prefixed 40-hex-character strings.
    Returns the address lowercased for consistency.
    """
    if not EVM_ADDRESS_RE.match(value):
        raise ValueError(
            f"Invalid EVM wallet address: {value!r}. "
            "Must be 0x-prefixed and exactly 40 hex characters."
        )
    return value.lower()


def _validate_solana_address(value: str) -> str:
    """Require a base58-encoded 32-byte Solana public key."""
    if not 32 <= len(value) <= 44:
        raise ValueError("Invalid Solana address: expected a 32-byte public key.")
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    decoded = 0
    for character in value:
        digit = alphabet.find(character)
        if digit < 0:
            raise ValueError("Invalid Solana address: expected base58 encoding.")
        decoded = decoded * 58 + digit
    decoded_bytes = decoded.to_bytes((decoded.bit_length() + 7) // 8, "big")
    leading_zeroes = len(value) - len(value.lstrip("1"))
    if len(decoded_bytes) + leading_zeroes != 32:
        raise ValueError("Invalid Solana address: expected a 32-byte public key.")
    return value


#: Validated EVM wallet address — Annotated[str, ...] for full Pydantic v2 support.
WalletAddress = Annotated[str, AfterValidator(_validate_wallet_address)]

#: Base58-encoded 32-byte Solana public key.
SolanaAddress = Annotated[str, AfterValidator(_validate_solana_address)]


# ---------------------------------------------------------------------------
# Monetary amount — NEVER use floats for money
# ---------------------------------------------------------------------------


class MonetaryAmount(BaseModel):
    """A precise monetary value stored as an atomic integer.

    ``amount_atomic`` represents the value in the smallest indivisible unit
    of the currency (e.g. micro-USDX if decimals=6, so 1 USDX = 1_000_000).

    This prevents all floating-point precision errors in payment logic.
    """

    model_config = {"frozen": True}

    amount_atomic: int = Field(
        ge=0,
        description="Amount in the smallest indivisible unit of the currency.",
    )
    currency: Currency = Field(default=Currency.USDX)
    decimals: int = Field(
        default=USDX_DECIMALS,
        ge=0,
        le=18,
        description="Number of decimal places for the currency.",
    )

    @classmethod
    def from_decimal(
        cls,
        amount: Decimal | str,
        currency: Currency = Currency.USDX,
        decimals: int = USDX_DECIMALS,
    ) -> "MonetaryAmount":
        """Construct from a human-readable decimal string (e.g. '0.005')."""
        d = Decimal(str(amount))
        if d < 0:
            raise ValueError("Monetary amounts cannot be negative.")
        atomic = int(d * Decimal(10**decimals))
        return cls(amount_atomic=atomic, currency=currency, decimals=decimals)

    @classmethod
    def zero(cls, currency: Currency = Currency.USDX) -> "MonetaryAmount":
        return cls(amount_atomic=0, currency=currency)

    def to_decimal(self) -> Decimal:
        """Convert back to human-readable decimal."""
        return Decimal(self.amount_atomic) / Decimal(10**self.decimals)

    def __add__(self, other: "MonetaryAmount") -> "MonetaryAmount":
        self._assert_same_currency(other)
        return MonetaryAmount(
            amount_atomic=self.amount_atomic + other.amount_atomic,
            currency=self.currency,
            decimals=self.decimals,
        )

    def __lt__(self, other: "MonetaryAmount") -> bool:
        self._assert_same_currency(other)
        return self.amount_atomic < other.amount_atomic

    def __le__(self, other: "MonetaryAmount") -> bool:
        self._assert_same_currency(other)
        return self.amount_atomic <= other.amount_atomic

    def __gt__(self, other: "MonetaryAmount") -> bool:
        self._assert_same_currency(other)
        return self.amount_atomic > other.amount_atomic

    def __ge__(self, other: "MonetaryAmount") -> bool:
        self._assert_same_currency(other)
        return self.amount_atomic >= other.amount_atomic

    def _assert_same_currency(self, other: "MonetaryAmount") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare {self.currency} with {other.currency}."
            )

    def __str__(self) -> str:
        return f"{self.to_decimal()} {self.currency.value}"


# ---------------------------------------------------------------------------
# Annotated type aliases for use in Pydantic models
# ---------------------------------------------------------------------------

#: 402LXP payment scheme identifier
PaymentScheme = Annotated[str, Field(default="402LXP")]

#: Human-readable capability slug, e.g. "research.web-search"
CapabilitySlug = Annotated[
    str,
    Field(
        pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$",
        description=(
            "Dot-separated capability identifier, optionally ending with "
            "a wildcard segment. Example: 'research.web-search' or 'research.*'"
        ),
    ),
]
