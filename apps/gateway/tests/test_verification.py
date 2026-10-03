from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from paxrelay_domain import Currency, MonetaryAmount, Quote
from paxrelay_gateway.verification import verify_payment_proof
from paxrelay_paxeer import OfficialPaxeerAdapter


class AcceptingAdapter:
    async def verify_payment(self, proof: str, quote: dict) -> dict:
        assert quote["chain_id"] == 84532
        return {"verified": True}


@pytest.mark.asyncio
async def test_local_payment_check_uses_quote_chain_id() -> None:
    quote = Quote(
        tool_call_id=uuid4(),
        provider_id=uuid4(),
        service_version_id=uuid4(),
        amount=MonetaryAmount(
            amount_atomic=1_000_000,
            currency=Currency.USDX,
            decimals=6,
        ),
        chain_id=84532,
        recipient_address="0x" + "1" * 40,
        request_hash="0x" + "a" * 64,
        nonce="quote-nonce",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None),
    )
    proof = {
        "quote_id": str(quote.id),
        "request_hash": quote.request_hash,
        "amount_atomic": str(quote.amount.amount_atomic),
        "recipient": quote.recipient_address,
        "nonce": quote.nonce,
        "chain_id": quote.chain_id,
        "payment_scheme": "402LXP",
    }

    result = await verify_payment_proof(
        proof=json.dumps(proof),
        quote=quote,
        adapter=AcceptingAdapter(),
    )

    assert result == {"verified": True}


@pytest.mark.asyncio
async def test_official_adapter_builds_requirement_for_configured_chain() -> None:
    adapter = OfficialPaxeerAdapter(
        rpc_url="https://rpc.staging.example",
        layerx_api_url="https://layerx.staging.example",
        chain_id=84532,
    )
    quote = {
        "quote_id": str(uuid4()),
        "amount_atomic": 1_000_000,
        "currency": "USDX",
        "currency_decimals": 6,
        "recipient_address": "0x" + "1" * 40,
        "request_hash": "0x" + "a" * 64,
        "nonce": "quote-nonce",
        "expires_at": "2026-10-03T12:00:00Z",
        "chain_id": 84532,
    }

    requirement = await adapter.create_payment_requirement(quote)

    assert requirement["chain_id"] == 84532
