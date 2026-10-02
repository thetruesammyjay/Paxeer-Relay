"""Trusted public-key lookup and lifecycle checks for receipt verification.

The keyring contains public keys only. Keep its manifest in a controlled,
versioned configuration source and distribute updates to every verifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Literal

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from paxrelay_receipts.signing import curve_order
from paxrelay_receipts.verification import verify_receipt_signature


KeyStatus = Literal["active", "retired", "revoked"]


def _utc_datetime(
    value: datetime | str,
    field_name: str,
    *,
    require_offset: bool = False,
) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(
                value[:-1] + "+00:00" if value.endswith("Z") else value
            )
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 timestamp.") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp.")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if require_offset:
            raise ValueError(f"{field_name} must include a UTC offset.")
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _reject_duplicate_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate receipt keyring field: {key}.")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class ReceiptVerificationKey:
    """One public verification key and its trusted receipt-time window."""

    key_id: str
    public_key_pem: str
    status: KeyStatus
    not_before: datetime
    not_after: datetime | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key_id, str)
            or not self.key_id
            or self.key_id != self.key_id.strip()
            or len(self.key_id) > 128
        ):
            raise ValueError("Receipt verification key ID must be 1 to 128 characters.")
        if not isinstance(self.status, str) or self.status not in {
            "active",
            "retired",
            "revoked",
        }:
            raise ValueError("Receipt verification key status is invalid.")
        if not isinstance(self.public_key_pem, str) or not self.public_key_pem.strip():
            raise ValueError("Receipt verification key must contain a public PEM key.")

        not_before = _utc_datetime(
            self.not_before, "not_before", require_offset=True
        )
        not_after = (
            _utc_datetime(self.not_after, "not_after", require_offset=True)
            if self.not_after is not None
            else None
        )
        if not_after is not None and not_after <= not_before:
            raise ValueError("not_after must be later than not_before.")
        if self.status == "active" and not_after is not None:
            raise ValueError(
                "An active key cannot have not_after; retire it to set an end time."
            )
        if self.status == "retired" and not_after is None:
            raise ValueError("A retired key must have not_after.")

        try:
            public_key = serialization.load_pem_public_key(
                self.public_key_pem.encode("utf-8")
            )
        except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
            raise ValueError(
                "Receipt verification key is not a valid public PEM key."
            ) from exc
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise ValueError("Receipt verification key must be an EC public key.")
        try:
            curve_order(public_key.curve)
        except ValueError as exc:
            raise ValueError(
                "Receipt verification key uses an unsupported curve."
            ) from exc

        object.__setattr__(self, "not_before", not_before)
        object.__setattr__(self, "not_after", not_after)


class ReceiptKeyring:
    """Resolve receipt key IDs and enforce activation, retirement, and revocation."""

    _MANIFEST_FIELDS = {"version", "keys"}
    _KEY_FIELDS = {"key_id", "public_key_pem", "status", "not_before", "not_after"}

    def __init__(self, keys: list[ReceiptVerificationKey]) -> None:
        by_id: dict[str, ReceiptVerificationKey] = {}
        for key in keys:
            if key.key_id in by_id:
                raise ValueError(f"Duplicate receipt verification key ID: {key.key_id}.")
            by_id[key.key_id] = key

        active_keys = [key for key in keys if key.status == "active"]
        if len(active_keys) > 1:
            raise ValueError("A receipt keyring may contain at most one active key.")

        time_limited_keys = sorted(
            (key for key in keys if key.status in {"active", "retired"}),
            key=lambda key: key.not_before,
        )
        for previous, following in zip(time_limited_keys, time_limited_keys[1:]):
            if previous.not_after is None or previous.not_after > following.not_before:
                raise ValueError(
                    "Receipt verification key validity windows must not overlap."
                )

        self._keys = MappingProxyType(by_id)

    @classmethod
    def from_json(cls, manifest_json: str) -> "ReceiptKeyring":
        """Load a version 1 JSON keyring manifest; reject duplicate/unknown fields."""
        try:
            manifest = json.loads(
                manifest_json,
                object_pairs_hook=_reject_duplicate_fields,
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Receipt keyring manifest is not valid JSON.") from exc

        if not isinstance(manifest, dict) or set(manifest) != cls._MANIFEST_FIELDS:
            raise ValueError(
                "Receipt keyring manifest must contain only version and keys."
            )
        if type(manifest["version"]) is not int or manifest["version"] != 1:
            raise ValueError("Unsupported receipt keyring manifest version.")
        raw_keys = manifest["keys"]
        if not isinstance(raw_keys, list):
            raise ValueError("Receipt keyring keys must be a list.")

        keys: list[ReceiptVerificationKey] = []
        for index, raw_key in enumerate(raw_keys):
            if not isinstance(raw_key, dict) or set(raw_key) != cls._KEY_FIELDS:
                raise ValueError(
                    f"Receipt keyring entry {index} must contain exactly: "
                    "key_id, public_key_pem, status, not_before, and not_after."
                )
            not_before = raw_key["not_before"]
            not_after = raw_key["not_after"]
            if not isinstance(not_before, str):
                raise ValueError(
                    f"Receipt keyring entry {index} has invalid not_before."
                )
            if not_after is not None and not isinstance(not_after, str):
                raise ValueError(
                    f"Receipt keyring entry {index} has invalid not_after."
                )
            keys.append(
                ReceiptVerificationKey(
                    key_id=raw_key["key_id"],
                    public_key_pem=raw_key["public_key_pem"],
                    status=raw_key["status"],
                    not_before=_utc_datetime(
                        not_before,
                        f"keys[{index}].not_before",
                        require_offset=True,
                    ),
                    not_after=(
                        _utc_datetime(
                            not_after,
                            f"keys[{index}].not_after",
                            require_offset=True,
                        )
                        if not_after is not None
                        else None
                    ),
                )
            )
        return cls(keys)

    def to_json(self) -> str:
        """Serialize a deterministic public-key manifest suitable for distribution."""
        keys = []
        for key in sorted(self._keys.values(), key=lambda item: item.key_id):
            keys.append(
                {
                    "key_id": key.key_id,
                    "public_key_pem": key.public_key_pem,
                    "status": key.status,
                    "not_before": key.not_before.isoformat().replace("+00:00", "Z"),
                    "not_after": (
                        key.not_after.isoformat().replace("+00:00", "Z")
                        if key.not_after is not None
                        else None
                    ),
                }
            )
        return json.dumps({"version": 1, "keys": keys}, indent=2) + "\n"

    def verify(self, receipt: dict) -> tuple[bool, str]:
        """Verify a receipt using its key ID and the manifest's lifecycle rules."""
        if not isinstance(receipt, dict):
            return False, "invalid_receipt"

        key_id = receipt.get("signing_key_id")
        if not isinstance(key_id, str) or not key_id:
            return False, "signing_key_id_missing_or_invalid"
        key = self._keys.get(key_id)
        if key is None:
            return False, "unknown_signing_key"
        if key.status == "revoked":
            return False, "signing_key_revoked"

        try:
            issued_at = _utc_datetime(receipt.get("issued_at"), "issued_at")
        except ValueError:
            return False, "receipt_issued_at_invalid"
        if issued_at < key.not_before:
            return False, "signing_key_not_yet_valid"
        if key.not_after is not None and issued_at >= key.not_after:
            return False, "signing_key_expired"

        signature = receipt.get("signature")
        if not isinstance(signature, str):
            return False, "signature_missing_or_invalid"
        return verify_receipt_signature(receipt, signature, key.public_key_pem)
