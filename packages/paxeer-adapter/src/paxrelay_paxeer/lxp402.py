"""402LXP payment requirement generation and proof verification helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any


def generate_nonce() -> str:
    """Generate a cryptographically random nonce for replay protection."""
    return "0x" + secrets.token_hex(32)


def hash_request_body(body: bytes) -> str:
    """Produce a SHA-256 hex digest of the canonical request body."""
    return "0x" + hashlib.sha256(body).hexdigest()


def build_payment_requirement(
    quote_id: str,
    amount_atomic: int,
    currency: str,
    currency_decimals: int,
    recipient_address: str,
    request_hash: str,
    nonce: str,
    expires_at: datetime,
    chain_id: int = 125,
    settlement_layer: str = "layerx",
) -> dict[str, Any]:
    """Build the 402LXP payment requirement object returned in HTTP 402 responses.

    Matches the structure defined in the README exactly.
    """
    return {
        "version": "1",
        "payment_scheme": "402LXP",
        "network": "paxeer",
        "chain_id": chain_id,
        "settlement_layer": settlement_layer,
        "currency": currency,
        "currency_decimals": currency_decimals,
        "amount_atomic": str(amount_atomic),
        "recipient": recipient_address,
        "quote_id": quote_id,
        "request_hash": request_hash,
        "expires_at": expires_at.isoformat() + "Z",
        "nonce": nonce,
    }


def verify_requirement_fields(
    proof_claims: Any,
    expected_quote_id: str,
    expected_request_hash: str,
    expected_amount_atomic: int,
    expected_recipient: str,
    expected_nonce: str,
    expires_at: datetime,
    now: datetime | None = None,
    expected_chain_id: int = 125,
) -> tuple[bool, str]:
    """Validate all required fields of an incoming payment proof.

    Returns (is_valid, reason) tuple. On success reason is empty string.
    Implements the verification checklist from the README.
    """
    now = now or datetime.utcnow()

    # The proof is untrusted input. JSON may decode to a list, string, number,
    # or null, and individual claims may have the wrong type. Treat all of
    # those cases as an invalid proof instead of allowing attribute/type errors
    # to escape into the request handler as HTTP 500 responses.
    if not isinstance(proof_claims, dict):
        return False, "invalid_proof_format"

    if now >= expires_at:
        return False, "quote_expired"

    if proof_claims.get("quote_id") != expected_quote_id:
        return False, "quote_id_mismatch"

    if proof_claims.get("request_hash") != expected_request_hash:
        return False, "request_hash_mismatch"

    raw_amount = proof_claims.get("amount_atomic")
    if isinstance(raw_amount, bool):
        return False, "amount_mismatch"
    if isinstance(raw_amount, int):
        claimed_amount = raw_amount
    elif isinstance(raw_amount, str) and raw_amount.isdecimal():
        claimed_amount = int(raw_amount)
    else:
        return False, "amount_mismatch"
    if claimed_amount != expected_amount_atomic:
        return False, "amount_mismatch"

    recipient = proof_claims.get("recipient")
    if not isinstance(recipient, str) or recipient.lower() != expected_recipient.lower():
        return False, "recipient_mismatch"

    if proof_claims.get("nonce") != expected_nonce:
        return False, "nonce_mismatch"

    chain_id = proof_claims.get("chain_id")
    if (
        isinstance(chain_id, bool)
        or not isinstance(chain_id, int)
        or chain_id != expected_chain_id
    ):
        return False, "wrong_chain"

    if proof_claims.get("payment_scheme") != "402LXP":
        return False, "wrong_payment_scheme"

    return True, ""


def calculate_quote_ttl_seconds(ttl: int = 300) -> datetime:
    """Return expiry datetime for a new quote."""
    return datetime.utcnow() + timedelta(seconds=ttl)
