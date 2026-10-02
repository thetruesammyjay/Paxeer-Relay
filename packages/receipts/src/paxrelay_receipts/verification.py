"""Receipt signature verification."""

from __future__ import annotations

import hmac
import re

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)

from paxrelay_receipts.hashing import hash_receipt
from paxrelay_receipts.signing import curve_order


_HASH_RE = re.compile(r"^0x[0-9a-f]{64}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


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
    if not isinstance(public_key_pem, str):
        return False, "invalid_public_key"
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (TypeError, ValueError, UnsupportedAlgorithm):
        return False, "invalid_public_key"
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        return False, "invalid_public_key_type"
    try:
        order = curve_order(public_key.curve)
    except ValueError:
        return False, "unsupported_public_key_curve"

    # Re-compute the hash the same way the signer did
    try:
        receipt_hash = hash_receipt(receipt_dict)
    except (TypeError, ValueError, OverflowError):
        return False, "invalid_receipt"

    claimed_hash = receipt_dict.get("receipt_hash")
    if not isinstance(claimed_hash, str) or not _HASH_RE.fullmatch(claimed_hash):
        return False, "receipt_hash_missing_or_invalid"
    if not hmac.compare_digest(claimed_hash, receipt_hash):
        return False, "receipt_hash_mismatch"

    embedded_signature = receipt_dict.get("signature")
    if embedded_signature is not None and embedded_signature != signature_hex:
        return False, "signature_field_mismatch"

    hash_bytes = bytes.fromhex(receipt_hash[2:])  # strip 0x

    if (
        not isinstance(signature_hex, str)
        or not signature_hex.startswith("0x")
        or len(signature_hex) <= 2
        or len(signature_hex[2:]) % 2 != 0
        or not _HEX_RE.fullmatch(signature_hex[2:])
    ):
        return False, "invalid_signature_encoding"
    try:
        sig_bytes = bytes.fromhex(signature_hex[2:])
        r, s = decode_dss_signature(sig_bytes)
    except ValueError:
        return False, "invalid_signature_encoding"
    if (
        encode_dss_signature(r, s) != sig_bytes
        or not 0 < r < order
        or not 0 < s <= order // 2
    ):
        return False, "invalid_signature_encoding"

    try:
        public_key.verify(
            sig_bytes,
            hash_bytes,
            ec.ECDSA(Prehashed(hashes.SHA256())),
        )
        return True, ""
    except InvalidSignature:
        return False, "signature_invalid"
    except (TypeError, ValueError):
        return False, "verification_error"
