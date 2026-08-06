"""LayerX stub routes — simulate settlement records and batch queries."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter(prefix="/layerx", tags=["layerx"])


@router.get("/settlement/{settlement_id}")
async def get_settlement(settlement_id: str) -> dict:
    """Return a simulated LayerX settlement record."""
    return {
        "settlement_id": settlement_id,
        "status": "settled",
        "transaction_hash": "0x" + secrets.token_hex(32),
        "batch_id": str(uuid.uuid4()),
        "block_number": 1_234_567,
        "block_hash": "0x" + secrets.token_hex(32),
        "settled_at": datetime.now(UTC).isoformat(),
        "chain_id": 125,
    }


@router.get("/batch/{batch_id}")
async def get_batch(batch_id: str) -> dict:
    """Return a simulated LayerX batch."""
    return {
        "batch_id": batch_id,
        "status": "finalized",
        "transaction_count": 1,
        "root_hash": "0x" + secrets.token_hex(32),
        "finalized_at": datetime.now(UTC).isoformat(),
    }


@router.post("/batch/{batch_id}/verify-l1")
async def verify_l1_commitment(batch_id: str, commitment_hash: str = "") -> dict:
    """Confirm that a batch's commitment hash is anchored on Paxeer L1."""
    return {
        "batch_id": batch_id,
        "commitment_hash": commitment_hash,
        "anchored": True,
        "l1_block": 7_890_123,
        "verified_at": datetime.now(UTC).isoformat(),
    }
