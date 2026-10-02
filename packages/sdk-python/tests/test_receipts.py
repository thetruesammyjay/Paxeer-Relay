from __future__ import annotations

import json
from pathlib import Path

from paxrelay import (
    ReceiptKeyring,
    ReceiptVerificationResult,
    verify_receipt,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VECTOR_PATH = REPOSITORY_ROOT / "docs" / "vectors" / "receipt-v1.json"
PUBLIC_KEY_PATH = REPOSITORY_ROOT / "docs" / "vectors" / "receipt-v1-public.pem"


def load_receipt() -> dict:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def load_keyring() -> ReceiptKeyring:
    manifest = {
        "version": 1,
        "keys": [
            {
                "key_id": "vector-only-key",
                "public_key_pem": PUBLIC_KEY_PATH.read_text(encoding="utf-8"),
                "status": "active",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": None,
            }
        ],
    }
    return ReceiptKeyring.from_json(json.dumps(manifest))


def test_sdk_verifies_a_receipt_with_the_trusted_keyring() -> None:
    result = verify_receipt(load_receipt(), load_keyring())

    assert result == ReceiptVerificationResult(valid=True, reason="")


def test_sdk_reports_a_tampered_receipt() -> None:
    receipt = load_receipt()
    receipt["routing"]["score"] = 0.726

    result = verify_receipt(receipt, load_keyring())

    assert result.valid is False
    assert result.reason == "receipt_hash_mismatch"


def test_sdk_rejects_a_non_mapping_receipt() -> None:
    result = verify_receipt([], load_keyring())  # type: ignore[arg-type]

    assert result == ReceiptVerificationResult(valid=False, reason="invalid_receipt")
