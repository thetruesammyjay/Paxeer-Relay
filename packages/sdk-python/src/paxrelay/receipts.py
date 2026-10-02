"""Receipt verification helpers exposed by the PaxRelay Python SDK."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from paxrelay_receipts import ReceiptKeyring


@dataclass(frozen=True, slots=True)
class ReceiptVerificationResult:
    """Outcome of verifying a receipt against a trusted public-key keyring."""

    valid: bool
    reason: str = ""


def verify_receipt(
    receipt: Mapping[str, Any],
    keyring: ReceiptKeyring,
) -> ReceiptVerificationResult:
    """Verify receipt content, signature, and signing-key lifecycle policy.

    The receipt must be the full signed receipt object, including its
    ``receipt_hash``, ``signature``, ``signing_key_id``, and ``issued_at``.
    The caller is responsible for obtaining the keyring from a trusted API
    origin or configuration channel and recording any result it needs.
    """
    if not isinstance(receipt, Mapping):
        return ReceiptVerificationResult(False, "invalid_receipt")

    valid, reason = keyring.verify(dict(receipt))
    return ReceiptVerificationResult(valid, reason)


async def fetch_receipt_keyring(
    receipt_keys_url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> ReceiptKeyring:
    """Fetch and validate a public receipt keyring manifest.

    Use the full `/v1/receipt-keys` URL from a trusted PaxRelay API origin.
    HTTPS is required except for loopback URLs used during local development.
    The caller should fetch again when it needs to apply a rotation or
    revocation; the API marks the manifest as non-cacheable.
    """
    _validate_receipt_keys_url(receipt_keys_url)
    if client is not None:
        return await _fetch_receipt_keyring(client, receipt_keys_url)

    async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as owned_client:
        return await _fetch_receipt_keyring(owned_client, receipt_keys_url)


async def _fetch_receipt_keyring(
    client: httpx.AsyncClient,
    receipt_keys_url: str,
) -> ReceiptKeyring:
    response = await client.get(
        receipt_keys_url,
        headers={"Cache-Control": "no-cache"},
        follow_redirects=False,
    )
    response.raise_for_status()
    if len(response.content) > 262_144:
        raise ValueError("Receipt verification keyring response is too large.")
    return ReceiptKeyring.from_json(response.text)


def _validate_receipt_keys_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        _ = parsed.port
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Receipt keyring URL must be a valid HTTPS URL.") from exc

    if (
        not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Receipt keyring URL must not contain credentials or query data.")

    local_http = parsed.scheme == "http" and hostname.lower() in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if parsed.scheme != "https" and not local_http:
        raise ValueError("Receipt keyring URLs must use HTTPS outside loopback development.")
