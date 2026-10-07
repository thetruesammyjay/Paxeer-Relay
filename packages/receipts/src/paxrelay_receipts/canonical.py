"""Canonical JSON serialization for PaxRelay receipt hashing.

Receipt v1 and v2 use compact UTF-8 JSON with recursively sorted object keys. UUIDs
are lowercase hyphenated strings. Timestamps are UTC ISO-8601 strings with six
fractional digits and a ``Z`` suffix. Integers remain exact base-10 JSON
integers; finite floating-point values use their shortest round-trip decimal
written without exponent notation. This keeps the route score interoperable
without converting amounts to floating point.

The receipt hash omits ``signature``, ``receipt_hash``, and
``signing_key_id``. Any implementation verifying receipts must apply these
same rules before computing SHA-256.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def _canonical_datetime(value: datetime) -> str:
    """Return a fixed-precision UTC timestamp.

    Naive timestamps in existing domain records represent UTC. Keep that
    interpretation for compatibility, while converting aware timestamps
    from their supplied offset to UTC.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_receipt_datetime(value: Any, field_name: str) -> Any:
    """Normalize a timestamp already serialized in a receipt JSON document."""
    if not isinstance(value, str):
        return value
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError as exc:
        raise ValueError(f"Receipt field {field_name!r} must be an ISO-8601 timestamp.") from exc
    return parsed


def _canonical_value(value: Any) -> Any:
    """Convert receipt-specific types to JSON values before encoding."""
    if isinstance(value, datetime):
        return _canonical_datetime(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Canonical JSON object keys must be strings.")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, Decimal, str)):
        return value
    raise TypeError(f"Unsupported value in canonical receipt: {type(value).__name__}.")


def _number_token(value: int | float | Decimal) -> str:
    """Emit an exact integer or normalized finite decimal JSON number."""
    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite floats are not valid in canonical JSON.")
        decimal_value = Decimal(str(value))
    else:
        decimal_value = value

    if not decimal_value.is_finite():
        raise ValueError("Non-finite decimals are not valid in canonical JSON.")
    if decimal_value.is_zero():
        return "0"

    token = format(decimal_value, "f")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token


def _json_token(value: Any) -> str:
    """Encode a canonical value without relying on runtime dict order."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float, Decimal)):
        return _number_token(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_json_token(item) for item in value) + "]"
    if isinstance(value, dict):
        # UTF-16 code-unit ordering is stable across common JSON runtimes.
        keys = sorted(value, key=lambda key: key.encode("utf-16-be"))
        members = (
            json.dumps(key, ensure_ascii=False) + ":" + _json_token(value[key])
            for key in keys
        )
        return "{" + ",".join(members) + "}"
    raise TypeError(f"Unsupported value in canonical receipt: {type(value).__name__}.")


def canonical_json(data: dict[str, Any]) -> bytes:
    """Produce compact, deterministic UTF-8 JSON bytes.

    Floating-point values are represented as JSON numbers, never strings.
    Their decimal tokens are normalized so ``1.0`` and ``1`` hash the same
    numeric value, negative zero becomes ``0``, and exponent notation is not
    emitted. Integer amounts remain exact, including values larger than the
    JavaScript safe-integer range.
    """
    if not isinstance(data, dict):
        raise TypeError("Canonical JSON input must be an object.")
    canonical = _canonical_value(data)
    try:
        return _json_token(canonical).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Canonical JSON strings must contain valid Unicode.") from exc


def receipt_to_canonical(receipt_dict: dict[str, Any]) -> bytes:
    """Prepare a full receipt object for hashing.

    Timestamp strings from a JSON/API response are parsed and normalized in
    the same way as datetime instances from the domain model. This lets a
    client verify a serialized receipt without reproducing Pydantic's JSON
    formatting details.
    """
    if not isinstance(receipt_dict, dict):
        raise TypeError("Receipt input must be an object.")

    stripped = {
        key: value
        for key, value in receipt_dict.items()
        if key not in ("signature", "receipt_hash", "signing_key_id")
    }

    if "issued_at" in stripped:
        stripped["issued_at"] = _parse_receipt_datetime(
            stripped["issued_at"], "issued_at"
        )
    execution = stripped.get("execution")
    if isinstance(execution, dict):
        execution = dict(execution)
        for field_name in ("started_at", "completed_at"):
            if field_name in execution:
                execution[field_name] = _parse_receipt_datetime(
                    execution[field_name], f"execution.{field_name}"
                )
        stripped["execution"] = execution

    return canonical_json(stripped)
