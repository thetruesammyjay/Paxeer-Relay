"""Receipt signing using ECDSA (secp256k1 via cryptography library).

LocalReceiptSigner reads a PEM-encoded private key from the environment
and signs the SHA-256 hash of the canonical receipt JSON.

Future: KMSReceiptSigner can be plugged in transparently.
"""

from __future__ import annotations

import base64
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from paxrelay_receipts.hashing import hash_receipt


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
        self._key_id = key_id
        self._private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, receipt_dict: dict) -> tuple[str, str]:
        """Canonicalize, hash, and sign the receipt.

        Returns:
            (receipt_hash, signature_hex) where both are 0x-prefixed hex strings.
        """
        receipt_hash = hash_receipt(receipt_dict)

        # Sign the raw hash bytes (strip leading 0x)
        hash_bytes = bytes.fromhex(receipt_hash[2:])

        signature_der = self._private_key.sign(  # type: ignore[union-attr]
            hash_bytes,
            ec.ECDSA(hashes.Prehashed()),
        )

        # Encode as hex for storage
        signature_hex = "0x" + signature_der.hex()
        return receipt_hash, signature_hex

    @staticmethod
    def generate_key_pem() -> str:
        """Generate a new P-256 private key and return it as PEM string.

        Useful for generating the RECEIPT_SIGNING_PRIVATE_KEY env var.
        """
        key = ec.generate_private_key(ec.SECP256K1())
        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
