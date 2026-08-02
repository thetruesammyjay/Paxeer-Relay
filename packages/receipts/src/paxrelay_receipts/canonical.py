"""Canonical JSON serialization for receipt signing.

Before signing a receipt:
1. Remove the signature field.
2. Sort object keys deterministically.
3. Encode numbers as strings, timestamps as ISO-8601 UTC.
4. Serialise using canonical JSON (no extra whitespace).

This ensures the hash is reproducible across any language or runtime.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID


def _canonical_value(v: Any) -> Any:
    """Recursively convert a value to a canonical JSON-serialisable form."""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, dict):
        return {str(k): _canonical_value(val) for k, val in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_canonical_value(i) for i in v]
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        raise ValueError(
            f"Float values are forbidden in receipts: {v!r}. "
            "Use integer atomic amounts only."
        )
    return v


def canonical_json(data: dict[str, Any]) -> bytes:
    """Produce the canonical JSON bytes for a receipt or sub-object.

    Keys are sorted alphabetically at every depth level.
    The result is UTF-8 encoded with no extra whitespace.
    """
    canonical = _canonical_value(data)
    return json.dumps(canonical, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def receipt_to_canonical(receipt_dict: dict[str, Any]) -> bytes:
    """Prepare a receipt dict for hashing.

    Per spec: remove 'signature', 'receipt_hash', and 'signing_key_id'
    before canonicalization.
    """
    stripped = {
        k: v
        for k, v in receipt_dict.items()
        if k not in ("signature", "receipt_hash", "signing_key_id")
    }
    return canonical_json(stripped)
