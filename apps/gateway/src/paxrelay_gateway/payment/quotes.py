"""Quote construction for the 402LXP payment challenge.

A quote is a time-limited, single-use payment requirement bound to exactly one
request hash, provider, service version, amount, and nonce.
"""

from __future__ import annotations

from uuid import UUID

from paxrelay_domain import MonetaryAmount, Quote
from paxrelay_paxeer import calculate_quote_ttl_seconds, generate_nonce


def build_quote(
    *,
    tool_call_id: UUID,
    provider_id: UUID,
    service_version_id: UUID,
    amount: MonetaryAmount,
    recipient_address: str,
    request_hash: str,
    ttl_seconds: int = 300,
    chain_id: int = 125,
) -> Quote:
    """Create a fresh, immutable :class:`Quote` for a tool call."""
    return Quote(
        tool_call_id=tool_call_id,
        provider_id=provider_id,
        service_version_id=service_version_id,
        amount=amount,
        chain_id=chain_id,
        recipient_address=recipient_address,
        request_hash=request_hash,
        nonce=generate_nonce(),
        expires_at=calculate_quote_ttl_seconds(ttl_seconds),
    )


def quote_to_requirement_input(quote: Quote) -> dict:
    """Shape a quote into the dict the Paxeer adapter's requirement builder wants."""
    return {
        "quote_id": str(quote.id),
        "tool_call_id": str(quote.tool_call_id),
        "amount_atomic": quote.amount.amount_atomic,
        "currency": quote.amount.currency.value,
        "currency_decimals": quote.amount.decimals,
        "recipient_address": quote.recipient_address,
        "request_hash": quote.request_hash,
        "nonce": quote.nonce,
        "expires_at": quote.expires_at.isoformat() + "Z",
        "chain_id": quote.chain_id,
    }
