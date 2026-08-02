"""Payment proof verification — the fail-closed 402LXP check.

Two layers, both must pass:
  1. Local field checklist (quote/request_hash/amount/recipient/nonce/chain).
  2. On-chain verification via the Paxeer adapter (Mock or Official).
"""

from __future__ import annotations

import json
from datetime import datetime

from paxrelay_domain import Quote
from paxrelay_paxeer import MockPaxeerAdapter, verify_requirement_fields

from paxrelay_gateway.payment.quotes import quote_to_requirement_input


class VerificationError(Exception):
    """Raised when a payment proof fails verification."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def verify_payment_proof(
    *,
    proof: str,
    quote: Quote,
    adapter: MockPaxeerAdapter,
) -> dict:
    """Verify a payment proof against a quote using the adapter.

    Returns the adapter's verification result (``{"verified": True, ...}`` on
    success). Raises :class:`VerificationError` with a stable reason code on
    any failure.
    """
    # Parse the proof (JSON string from the agent).
    try:
        proof_claims = json.loads(proof)
    except Exception as exc:
        raise VerificationError("invalid_proof_format") from exc

    # 1. Local checklist.
    ok, reason = verify_requirement_fields(
        proof_claims=proof_claims,
        expected_quote_id=str(quote.id),
        expected_request_hash=quote.request_hash,
        expected_amount_atomic=quote.amount.amount_atomic,
        expected_recipient=quote.recipient_address,
        expected_nonce=quote.nonce,
        expires_at=quote.expires_at,
        now=datetime.utcnow(),
    )
    if not ok:
        raise VerificationError(reason)

    # 2. On-chain verification via the adapter (quote shaped for the adapter).
    result = await adapter.verify_payment(proof, quote_to_requirement_input(quote))
    if not result.get("verified"):
        raise VerificationError(str(result.get("reason", "verification_failed")))

    return result
