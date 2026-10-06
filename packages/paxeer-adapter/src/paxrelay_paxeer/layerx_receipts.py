"""LayerX 402LXP v2 receipt verification through the official Python SDK."""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

from paxrelay_paxeer.errors import AdapterConfigurationError

_HEX_32 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_DOMAIN = b"LXP/v1/merkle-leaf\0"


class _Ed25519Verifier:
    """Small crypto provider required by LayerX's local receipt verifier."""

    def verify_ed25519(
        self, public_key: bytes, signature: bytes, digest: bytes
    ) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, digest)
            return True
        except (InvalidSignature, ValueError):
            return False

    def verify_recoverable_secp256k1(
        self,
        public_key: bytes,
        signature: bytes,
        signature_v: int,
        signer: bytes,
        digest: bytes,
    ) -> bool:
        del public_key, signature, signature_v, signer, digest
        return False


class LayerXReceiptVerifier:
    """Verify exact-payment receipts against an operator-pinned sequencer key.

    This integration deliberately supports only `exact` / `executed` receipts.
    The upstream SDK does not expose a public receipt-context decoder yet, so
    this adapter pins the SDK source revision and uses its private decoder only
    to extract signed receipt fields. The SDK's public payment verifier then
    checks canonical encoding, signature, amount, asset, recipient and payer.
    """

    def __init__(self, *, network_id: int, sequencer_public_key: str) -> None:
        sequencer_public_key = sequencer_public_key.lower()
        if type(network_id) is not int or not 1 <= network_id <= 0xFFFF_FFFF:
            raise AdapterConfigurationError("layerx_network_id_invalid")
        if _HEX_32.fullmatch(sequencer_public_key) is None:
            raise AdapterConfigurationError("layerx_sequencer_key_invalid")
        try:
            from layerx_sdk.x402 import verify_payment_receipt
            from layerx_sdk.x402_http import PaymentEvidence
            from layerx_sdk.verifier import AuthorizedReceiptBatch, _decode_protocol_receipt
        except ImportError as exc:
            raise AdapterConfigurationError("official_layerx_sdk_unavailable") from exc

        self.network_id = network_id
        self.sequencer_public_key = bytes.fromhex(sequencer_public_key)
        self._signatures = _Ed25519Verifier()
        self._payment_evidence_type = PaymentEvidence
        self._authorized_batch_type = AuthorizedReceiptBatch
        self._decode_protocol_receipt = _decode_protocol_receipt
        self._verify_payment_receipt = verify_payment_receipt

    @property
    def network(self) -> str:
        return f"layerx:{self.network_id}"

    def resolve_receipt(self, canonical_receipt: bytes, offer: dict[str, Any]) -> Any:
        """Build SDK verification context using the pinned sequencer authority."""
        del offer
        receipt, _ = self._decode_protocol_receipt(canonical_receipt)
        authorized = self._authorized_batch_type(
            batch_id=receipt.batch_id,
            asset=receipt.asset,
            previous_state_root=receipt.previous_state_root,
            resulting_state_root=receipt.resulting_state_root,
            sequencer_public_key=self.sequencer_public_key,
        )
        return self._payment_evidence_type(canonical_receipt, authorized)

    def verify_payment_signature(
        self,
        *,
        payment_required: dict[str, Any],
        payment_signature: str,
        expected_asset: str,
        expected_pay_to: str,
        expected_payer: str | None,
        expected_resource_url: str,
    ) -> dict[str, Any]:
        """Verify an SDK-produced PAYMENT-SIGNATURE against a stored quote."""
        try:
            from layerx_sdk.x402 import payment_commitment, payment_payer
            from layerx_sdk.x402_http import decode_header, validate_payload, validate_required

            required = validate_required(payment_required)
            payload = validate_payload(decode_header(payment_signature))
            if (
                payload.get("resource") != required["resource"]
                or required["resource"].get("url") != expected_resource_url
            ):
                raise ValueError("resource_mismatch")
            if payload.get("extensions", {}) != required.get("extensions", {}):
                raise ValueError("extensions_mismatch")
            offer = payload["accepted"]
            if offer not in required["accepts"]:
                raise ValueError("offer_mismatch")
            if (
                offer["scheme"] != "exact"
                or offer["network"] != self.network
                or offer["asset"] != expected_asset
                or offer["payTo"] != expected_pay_to
                or payment_commitment(offer.get("extra")) != "executed"
            ):
                raise ValueError("unsupported_payment_terms")
            offered_payer = payment_payer(offer.get("extra"))
            if expected_payer is not None and offered_payer != expected_payer:
                raise ValueError("payer_offer_mismatch")

            body = payload["payload"]
            required_body_keys = {"receipt", "receiptDigest", "verificationLevel"}
            if set(body) not in (required_body_keys, required_body_keys | {"idempotencyKey"}):
                raise ValueError("invalid_payment_payload")
            if body["verificationLevel"] != "sequencer-signed":
                raise ValueError("invalid_verification_level")
            canonical_receipt = base64.b64decode(body["receipt"], validate=True)
            receipt_digest = hashlib.sha256(_RECEIPT_DOMAIN + canonical_receipt).hexdigest()
            if body["receiptDigest"] != receipt_digest:
                raise ValueError("receipt_digest_mismatch")

            evidence = self.resolve_receipt(canonical_receipt, offer)
            decoded_receipt, _ = self._decode_protocol_receipt(canonical_receipt)
            # An x402 payment must be the successful Asset send itself. The
            # SDK's general payment verifier checks receipt values and proof,
            # but accepts receipts from other modules if their transfer fields
            # happen to match.
            if (
                decoded_receipt.module_id != 1
                or decoded_receipt.operation != 5
                or decoded_receipt.result_code != 0
            ):
                raise ValueError("asset_send_receipt_required")
            verified = self._verify_payment_receipt(
                canonical_receipt,
                evidence.authorized_batch,
                self._signatures,
                amount=offer["amount"],
                asset=expected_asset,
                pay_to=expected_pay_to,
                payer=expected_payer or offered_payer,
                commitment="executed",
            )
            return {
                "verified": True,
                "layerx_transaction_hash": "0x" + verified.receipt.activity_id.hex(),
                "layerx_batch_id": "0x" + verified.receipt.batch_id.hex(),
                "layerx_receipt_digest": receipt_digest,
                "layerx_receipt": body["receipt"],
                "settlement_reference": "lxp:" + receipt_digest,
                "amount_atomic": str(verified.receipt.amount),
                "asset": verified.receipt.asset.hex(),
                "payer": verified.receipt.from_account.hex(),
                "pay_to": verified.receipt.to_account.hex(),
                "verification_level": verified.level,
            }
        except Exception as exc:  # SDK refusal details are untrusted input.
            reason = str(exc)
            if not reason or len(reason) > 80 or not re.fullmatch(r"[a-zA-Z0-9_.-]+", reason):
                reason = "invalid_payment_signature"
            return {"verified": False, "reason": reason}

    def buyer_middleware(self, rpc: Any) -> Any:
        """Create the official SDK buyer for an exact payment on this network."""
        from layerx_sdk.x402_http import BuyerMiddleware

        return BuyerMiddleware(
            rpc,
            self._signatures,
            self.resolve_receipt,
            {("exact", self.network)},
        )


def build_payment_required(
    *,
    resource_url: str,
    network: str,
    amount_atomic: int,
    asset: str,
    pay_to: str,
    timeout_seconds: int,
    payer: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Build the exact 402LXP v2 challenge and encode it with the official SDK."""
    from layerx_sdk.x402_http import encode_header, validate_required

    if (
        not isinstance(network, str)
        or not re.fullmatch(r"layerx:[1-9][0-9]*", network)
        or type(amount_atomic) is not int
        or not 0 < amount_atomic < 1 << 128
        or _HEX_32.fullmatch(asset) is None
        or _HEX_32.fullmatch(pay_to) is None
        or type(timeout_seconds) is not int
        or not 0 < timeout_seconds < 1 << 32
        or (
            payer is not None
            and (_HEX_32.fullmatch(payer) is None or payer == "0" * 64)
        )
    ):
        raise AdapterConfigurationError("layerx_payment_requirement_invalid")
    required = {
        "x402Version": 2,
        "resource": {"url": resource_url},
        "accepts": [
            {
                "scheme": "exact",
                "network": network,
                "amount": str(amount_atomic),
                "asset": asset,
                "payTo": pay_to,
                "maxTimeoutSeconds": timeout_seconds,
                "extra": {
                    "layerx": {
                        "commitment": "executed",
                        **({"payer": payer} if payer is not None else {}),
                    }
                },
            }
        ],
    }
    validate_required(required)
    return required, encode_header(required)
