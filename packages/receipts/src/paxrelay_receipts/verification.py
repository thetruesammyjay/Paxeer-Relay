"""Receipt signature verification."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from paxrelay_receipts.hashing import hash_receipt


def verify_receipt_signature(
    receipt_dict: dict,
    signature_hex: str,
    public_key_pem: str,
) -> tuple[bool, str]:
    """Verify the ECDSA signature of a receipt.

    Re-canonicalizes and re-hashes the receipt (with signature removed),
    then verifies the provided signature against the public key.

    Returns:
        (is_valid, reason) — reason is empty string on success.
    """
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception as exc:
        return False, f"invalid_public_key: {exc}"

    # Re-compute the hash the same way the signer did
    receipt_hash = hash_receipt(receipt_dict)
    hash_bytes = bytes.fromhex(receipt_hash[2:])  # strip 0x

    try:
        sig_bytes = bytes.fromhex(signature_hex.lstrip("0x"))
    except ValueError:
        return False, "invalid_signature_encoding"

    try:
        public_key.verify(sig_bytes, hash_bytes, ec.ECDSA(hashes.Prehashed()))  # type: ignore[union-attr]
        return True, ""
    except InvalidSignature:
        return False, "signature_invalid"
    except Exception as exc:
        return False, f"verification_error: {exc}"
