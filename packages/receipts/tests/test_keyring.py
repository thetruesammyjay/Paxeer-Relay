from __future__ import annotations

import json
from pathlib import Path

import pytest

from paxrelay_receipts import ReceiptKeyring


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VECTOR_PATH = REPOSITORY_ROOT / "docs" / "vectors" / "receipt-v1.json"
PUBLIC_KEY_PATH = REPOSITORY_ROOT / "docs" / "vectors" / "receipt-v1-public.pem"


@pytest.fixture
def receipt() -> dict:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def public_key_pem() -> str:
    return PUBLIC_KEY_PATH.read_text(encoding="utf-8")


def make_keyring(
    public_key_pem: str,
    *,
    key_id: str = "vector-only-key",
    status: str = "active",
    not_before: str = "2026-10-01T00:00:00Z",
    not_after: str | None = None,
) -> ReceiptKeyring:
    manifest = {
        "version": 1,
        "keys": [
            {
                "key_id": key_id,
                "public_key_pem": public_key_pem,
                "status": status,
                "not_before": not_before,
                "not_after": not_after,
            }
        ],
    }
    return ReceiptKeyring.from_json(json.dumps(manifest))


def test_verifies_published_vector_with_active_key(
    receipt: dict,
    public_key_pem: str,
) -> None:
    result, reason = make_keyring(public_key_pem).verify(receipt)

    assert result is True
    assert reason == ""


def test_unknown_signing_key_is_rejected(receipt: dict, public_key_pem: str) -> None:
    receipt["signing_key_id"] = "untrusted-key"

    result, reason = make_keyring(public_key_pem).verify(receipt)

    assert result is False
    assert reason == "unknown_signing_key"


def test_revoked_signing_key_is_rejected(receipt: dict, public_key_pem: str) -> None:
    keyring = make_keyring(public_key_pem, status="revoked")

    result, reason = keyring.verify(receipt)

    assert result is False
    assert reason == "signing_key_revoked"


def test_key_cannot_verify_receipt_before_activation(
    receipt: dict,
    public_key_pem: str,
) -> None:
    keyring = make_keyring(public_key_pem, not_before="2026-10-01T10:01:00Z")

    result, reason = keyring.verify(receipt)

    assert result is False
    assert reason == "signing_key_not_yet_valid"


def test_retired_key_verifies_receipts_issued_before_retirement(
    receipt: dict,
    public_key_pem: str,
) -> None:
    keyring = make_keyring(
        public_key_pem,
        status="retired",
        not_after="2026-10-01T10:01:00Z",
    )

    result, reason = keyring.verify(receipt)

    assert result is True
    assert reason == ""


def test_retired_key_rejects_receipt_issued_at_retirement_cutover(
    receipt: dict,
    public_key_pem: str,
) -> None:
    receipt["issued_at"] = "2026-10-01T12:01:00+02:00"
    keyring = make_keyring(
        public_key_pem,
        status="retired",
        not_after="2026-10-01T10:00:00Z",
    )

    result, reason = keyring.verify(receipt)

    assert result is False
    assert reason == "signing_key_expired"


def test_overlapping_key_windows_are_rejected(public_key_pem: str) -> None:
    manifest = {
        "version": 1,
        "keys": [
            {
                "key_id": "old-key",
                "public_key_pem": public_key_pem,
                "status": "retired",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2026-10-03T00:00:00Z",
            },
            {
                "key_id": "new-key",
                "public_key_pem": public_key_pem,
                "status": "active",
                "not_before": "2026-10-02T00:00:00Z",
                "not_after": None,
            },
        ],
    }

    with pytest.raises(ValueError, match="validity windows must not overlap"):
        ReceiptKeyring.from_json(json.dumps(manifest))


def test_manifest_round_trip_is_stable(public_key_pem: str) -> None:
    keyring = make_keyring(public_key_pem)

    restored = ReceiptKeyring.from_json(keyring.to_json())

    assert restored.to_json() == keyring.to_json()


def test_duplicate_manifest_fields_are_rejected(public_key_pem: str) -> None:
    duplicate_version = '{"version":1,"version":1,"keys":[]}'

    with pytest.raises(ValueError, match="Duplicate receipt keyring field"):
        ReceiptKeyring.from_json(duplicate_version)

    duplicate_key_ids = {
        "version": 1,
        "keys": [
            {
                "key_id": "same-key",
                "public_key_pem": public_key_pem,
                "status": "active",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": None,
            },
            {
                "key_id": "same-key",
                "public_key_pem": public_key_pem,
                "status": "retired",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2026-10-02T00:00:00Z",
            },
        ],
    }
    with pytest.raises(ValueError, match="Duplicate receipt verification key ID"):
        ReceiptKeyring.from_json(json.dumps(duplicate_key_ids))
