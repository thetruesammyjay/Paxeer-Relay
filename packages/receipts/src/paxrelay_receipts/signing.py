"""Receipt signing with ECDSA over canonical receipt hashes.

LocalReceiptSigner reads a PEM-encoded private key from the environment
and signs the SHA-256 hash of the canonical receipt JSON.

Future: KMSReceiptSigner can be plugged in transparently.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)

from paxrelay_receipts.hashing import hash_receipt


_CURVE_ORDERS = {
    "secp256k1": int(
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16
    ),
    "secp256r1": int(
        "FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16
    ),
}


def curve_order(curve: ec.EllipticCurve) -> int:
    """Return the group order for the receipt signing curves we support."""
    if isinstance(curve, ec.SECP256K1):
        return _CURVE_ORDERS["secp256k1"]
    if isinstance(curve, ec.SECP256R1):
        return _CURVE_ORDERS["secp256r1"]
    raise ValueError("Receipt signatures support only secp256k1 and P-256 keys.")


@runtime_checkable
class ReceiptSigner(Protocol):
    """Signing backend protocol — pluggable for local, KMS, or HSM backends."""

    @property
    def key_id(self) -> str: ...

    def sign(self, receipt_dict: dict) -> tuple[str, str]:
        """Return (receipt_hash, signature_hex)."""
        ...


class LocalReceiptSigner:
    """ECDSA signer using a local secp256k1 or P-256 key from PEM string.

    Typical usage:
        key_pem = os.environ["RECEIPT_SIGNING_PRIVATE_KEY"]
        signer = LocalReceiptSigner(key_pem, key_id="local-dev-v1")
        receipt_hash, sig = signer.sign(receipt.model_dump())
    """

    def __init__(self, private_key_pem: str, key_id: str = "local-development") -> None:
        if not key_id.strip():
            raise ValueError("Receipt signing key ID cannot be empty.")
        self._key_id = key_id
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise ValueError("Receipt signing key must be an EC private key.")
        curve_order(private_key.curve)
        self._private_key = private_key

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def public_key_pem(self) -> str:
        """Return the matching public key PEM for trusted verifier manifests."""
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def sign(self, receipt_dict: dict) -> tuple[str, str]:
        """Canonicalize, hash, and sign the receipt.

        Returns:
            (receipt_hash, signature_hex) where both are 0x-prefixed hex strings.
        """
        receipt_hash = hash_receipt(receipt_dict)

        # Sign the raw hash bytes (strip leading 0x)
        hash_bytes = bytes.fromhex(receipt_hash[2:])

        signature_der = self._private_key.sign(
            hash_bytes,
            ec.ECDSA(Prehashed(hashes.SHA256())),
        )

        # ECDSA admits both (r, s) and (r, n-s). Store the low-S form so a
        # receipt has one canonical signature encoding.
        r, s = decode_dss_signature(signature_der)
        order = curve_order(self._private_key.curve)
        if s > order // 2:
            s = order - s
        signature_der = encode_dss_signature(r, s)

        # cryptography encodes ECDSA signatures as ASN.1 DER.
        signature_hex = "0x" + signature_der.hex()
        return receipt_hash, signature_hex

    @staticmethod
    def generate_key_pem() -> str:
        """Generate a new secp256k1 private key and return it as a PEM string.

        Useful for generating the RECEIPT_SIGNING_PRIVATE_KEY env var.
        """
        key = ec.generate_private_key(ec.SECP256K1())
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
