"""SHA-256 hashing for receipts and request/response bodies."""

from __future__ import annotations

import hashlib
from typing import Any

from paxrelay_receipts.canonical import canonical_json, receipt_to_canonical


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest prefixed with 0x."""
    return "0x" + hashlib.sha256(data).hexdigest()


def hash_receipt(receipt_dict: dict[str, Any]) -> str:
    """Canonicalize a receipt dict and return its SHA-256 hash.

    This is the value stored in receipt_hash and signed.
    """
    canonical_bytes = receipt_to_canonical(receipt_dict)
    return sha256_hex(canonical_bytes)


def hash_body(body: bytes) -> str:
    """Hash a raw request or response body."""
    return sha256_hex(body)


def hash_canonical_dict(data: dict[str, Any]) -> str:
    """Hash any dict after canonical JSON serialization."""
    return sha256_hex(canonical_json(data))
