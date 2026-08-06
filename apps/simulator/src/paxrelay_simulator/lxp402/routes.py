"""402LXP stub routes — generate and verify simulated payment requirements."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from paxrelay_simulator.config import get_settings

router = APIRouter(prefix="/lxp402", tags=["402lxp"])


class RequirementRequest(BaseModel):
    quote_id: str
    amount_atomic: int
    currency: str = "USDX"
    currency_decimals: int = 6
    recipient_address: str
    request_hash: str
    nonce: str
    expires_at: str
    chain_id: int = 125


class VerifyRequest(BaseModel):
    proof: str
    quote_id: str
    request_hash: str
    expected_amount_atomic: int
    expected_recipient: str
    expected_nonce: str


@router.post("/payment-requirement")
async def create_payment_requirement(body: RequirementRequest) -> dict:
    """Return a simulated 402LXP payment requirement envelope."""
    settings = get_settings()
    await _sim_delay(settings.payment_verify_delay_ms)
    return {
        "payment_requirement": {
            "quote_id": body.quote_id,
            "amount_atomic": body.amount_atomic,
            "currency": body.currency,
            "currency_decimals": body.currency_decimals,
            "recipient_address": body.recipient_address,
            "request_hash": body.request_hash,
            "nonce": body.nonce,
            "expires_at": body.expires_at,
            "chain_id": body.chain_id,
            "payment_url": f"layerx://pay/{body.quote_id}",
            "scheme": "402LXP/1.0",
        }
    }


@router.post("/verify")
async def verify_payment(body: VerifyRequest) -> dict:
    """Accept any well-formed proof and return a successful verification."""
    settings = get_settings()
    await _sim_delay(settings.payment_verify_delay_ms)

    import random
    if settings.failure_rate > 0 and random.random() < settings.failure_rate:
        return {"verified": False, "reason": "simulated_failure"}

    return {
        "verified": True,
        "quote_id": body.quote_id,
        "layerx_transaction_hash": "0x" + secrets.token_hex(32),
        "layerx_batch_id": str(uuid.uuid4()),
        "verified_at": datetime.now(UTC).isoformat(),
    }


async def _sim_delay(ms: int) -> None:
    import asyncio
    if ms > 0:
        await asyncio.sleep(ms / 1000)
