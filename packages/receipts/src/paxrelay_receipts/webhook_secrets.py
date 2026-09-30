"""Authenticated encryption helpers for webhook endpoint secrets.

Webhook delivery needs the original endpoint secret to sign payloads. Store
that value with authenticated encryption and bind each ciphertext to its
endpoint ID so a database row cannot be swapped between endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_VERSION = "v1"
_NONCE_BYTES = 12
_HKDF_SALT = b"paxrelay:webhook-secret-encryption:v1"
_HKDF_INFO = b"paxrelay-webhook-secret-ciphertext"


def _derive_key(master_key: str) -> bytes:
    if not master_key:
        raise ValueError("A webhook encryption key is required.")
    return HKDF(
        algorithm=SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(master_key.encode("utf-8"))


def _associated_data(endpoint_id: str) -> bytes:
    if not endpoint_id:
        raise ValueError("A webhook endpoint ID is required.")
    return f"paxrelay:webhook:{endpoint_id}:{_VERSION}".encode("utf-8")


def encrypt_webhook_secret(secret: str, master_key: str, endpoint_id: str) -> str:
    """Encrypt a webhook's shared secret and return a versioned text value."""
    if not secret:
        raise ValueError("A webhook secret is required.")

    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_derive_key(master_key)).encrypt(
        nonce,
        secret.encode("utf-8"),
        _associated_data(endpoint_id),
    )
    encoded = (
        base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
    )
    return f"{_VERSION}.{encoded}"


def decrypt_webhook_secret(
    ciphertext: str,
    master_key: str,
    endpoint_id: str,
) -> str:
    """Decrypt an endpoint secret, rejecting unknown versions and tampering."""
    try:
        version, encoded = ciphertext.split(".", maxsplit=1)
        if version != _VERSION:
            raise ValueError("Unsupported webhook secret ciphertext version.")
        packed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if len(packed) <= _NONCE_BYTES:
            raise ValueError("Invalid webhook secret ciphertext.")
        plaintext = AESGCM(_derive_key(master_key)).decrypt(
            packed[:_NONCE_BYTES],
            packed[_NONCE_BYTES:],
            _associated_data(endpoint_id),
        )
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Webhook secret could not be decrypted.") from exc


def webhook_secret_digest(secret: str) -> str:
    """Return a SHA-256 digest for identifying secret changes without exposing it."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
