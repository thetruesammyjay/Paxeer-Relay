"""Solana Devnet x402 V2 exact-payment adapter.

This adapter is deliberately Devnet-only. It uses the x402 SDK for the wire
objects, Solana transaction checks, facilitator verification, and settlement.
It never handles or stores a buyer signing key.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from x402.http import (
    FacilitatorConfig,
    HTTPFacilitatorClient,
    decode_payment_signature_header,
    encode_payment_required_header,
    encode_payment_response_header,
)
from x402.mechanisms.svm.exact import ExactSvmServerScheme
from x402.schemas import (
    AssetAmount,
    PaymentRequired,
    PaymentRequirements,
    ResourceConfig,
    ResourceInfo,
    SettleResponse,
)
from x402.server import x402ResourceServer

from paxrelay_paxeer.errors import AdapterConfigurationError, AdapterUnavailableError

SOLANA_DEVNET_NETWORK = "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"
SOLANA_DEVNET_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"


class SolanaX402Adapter:
    """Create, verify, and settle Devnet USDC exact-payment x402 offers."""

    supports_x402_solana = True
    payment_scheme = "exact"
    network = SOLANA_DEVNET_NETWORK
    settlement_layer = "solana-devnet"

    def __init__(
        self,
        *,
        facilitator_url: str,
        rpc_url: str,
        usdc_mint: str,
        gateway_public_base_url: str,
        facilitator_timeout_seconds: float = 15.0,
        max_amount_atomic: int = 10_000,
    ) -> None:
        if usdc_mint != SOLANA_DEVNET_USDC_MINT:
            raise AdapterConfigurationError("unsupported_solana_devnet_asset")
        if not 1 <= max_amount_atomic <= 10_000:
            raise AdapterConfigurationError("invalid_solana_devnet_payment_cap")
        self._gateway_public_base_url = gateway_public_base_url.rstrip("/")
        self._max_amount_atomic = max_amount_atomic
        facilitator = HTTPFacilitatorClient(
            FacilitatorConfig(
                url=facilitator_url,
                timeout=facilitator_timeout_seconds,
            )
        )
        self._server = x402ResourceServer(facilitator).register(
            self.network,
            ExactSvmServerScheme(rpc_url=rpc_url),
        )
        self._initialized = False
        self._initialization_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Check facilitator support before the gateway advertises this rail."""
        if self._initialized:
            return
        async with self._initialization_lock:
            if self._initialized:
                return
            try:
                await asyncio.to_thread(self._server.initialize)
            except Exception as exc:  # SDK exceptions vary by facilitator client.
                raise AdapterUnavailableError(
                    "solana_x402_facilitator_unavailable"
                ) from exc
            self._initialized = True

    async def create_payment_requirement(self, quote: dict[str, Any]) -> dict[str, Any]:
        await self.initialize()
        resource = self._resource_url(quote)
        amount_atomic = self._validated_amount(quote)
        config = ResourceConfig(
            scheme=self.payment_scheme,
            payTo=str(quote["recipient_address"]),
            price=AssetAmount(
                amount=str(amount_atomic),
                asset=SOLANA_DEVNET_USDC_MINT,
            ),
            network=self.network,
            maxTimeoutSeconds=self._remaining_timeout(quote),
        )
        try:
            requirements = self._server.build_payment_requirements(config)
            if len(requirements) != 1:
                raise AdapterConfigurationError("unexpected_solana_requirement_count")
            response = PaymentRequired(
                x402Version=2,
                resource=ResourceInfo(
                    url=resource,
                    description="PaxRelay paid service request",
                    mimeType="application/json",
                    serviceName="PaxRelay",
                ),
                accepts=requirements,
            )
        except AdapterConfigurationError:
            raise
        except Exception as exc:
            raise AdapterConfigurationError("invalid_solana_x402_offer") from exc
        return response.model_dump(mode="json", by_alias=True, exclude_none=True)

    def encode_payment_required(self, requirement: dict[str, Any]) -> str:
        return encode_payment_required_header(PaymentRequired.model_validate(requirement))

    async def verify_payment(self, proof: str, quote: dict[str, Any]) -> dict[str, Any]:
        """Verify then settle the exact offered payment before forwarding."""
        await self.initialize()
        try:
            payload = decode_payment_signature_header(proof)
            expected = self._expected_requirement(quote)
            expected_resource = self._resource_url(quote)
        except Exception:
            return {"verified": False, "reason": "invalid_solana_payment_payload"}

        accepted = payload.accepted
        if (
            payload.x402_version != 2
            or accepted.scheme != expected.scheme
            or accepted.network != expected.network
            or accepted.asset != expected.asset
            or accepted.amount != expected.amount
            or accepted.pay_to != expected.pay_to
            or accepted.max_timeout_seconds != expected.max_timeout_seconds
            or payload.resource is None
            or payload.resource.url != expected_resource
        ):
            return {"verified": False, "reason": "payment_requirements_mismatch"}

        try:
            verified = await self._server.verify_payment(payload, expected)
        except Exception as exc:  # A facilitator/network failure is not proof.
            raise AdapterUnavailableError("solana_x402_verification_unavailable") from exc
        if not verified.is_valid:
            return {
                "verified": False,
                "reason": verified.invalid_reason or "solana_payment_not_verified",
            }

        # Solana exact transfers must settle before PaxRelay calls the provider.
        try:
            settlement = await self._server.settle_payment(
                payload,
                expected,
                phase="before-handler",
            )
        except Exception as exc:
            raise AdapterUnavailableError("solana_x402_settlement_unavailable") from exc
        if not settlement.success:
            return {
                "verified": False,
                "reason": settlement.error_reason or "solana_payment_not_settled",
            }
        if (
            settlement.network != expected.network
            or (settlement.amount is not None and settlement.amount != expected.amount)
            or not settlement.transaction
        ):
            raise AdapterUnavailableError("solana_x402_malformed_settlement_response")

        result = {
            "verified": True,
            "solana_transaction_signature": settlement.transaction,
            "transaction": settlement.transaction,
            "network": settlement.network,
            "asset": expected.asset,
            "payer": settlement.payer,
            "amount": settlement.amount or expected.amount,
        }
        result["payment_response_header"] = self.encode_payment_response(result, quote)
        return result

    def encode_payment_response(
        self, verification: dict[str, Any], quote: dict[str, Any]
    ) -> str:
        settlement = SettleResponse(
            success=True,
            transaction=str(verification["transaction"]),
            network=str(verification.get("network") or self.network),
            amount=str(verification.get("amount") or quote["amount_atomic"]),
            payer=verification.get("payer"),
        )
        return encode_payment_response_header(settlement)

    def response_header_for_payment(self, payment: Any, quote: Any) -> str | None:
        """Rebuild a settlement response for an already-recorded payment."""
        transaction = payment.solana_transaction_signature
        if not transaction:
            return None
        return self.encode_payment_response(
            {
                "transaction": transaction,
                "network": quote.network,
                "amount": str(quote.amount.amount_atomic),
            },
            {"amount_atomic": quote.amount.amount_atomic},
        )

    def _expected_requirement(self, quote: dict[str, Any]) -> PaymentRequirements:
        amount_atomic = self._validated_amount(quote)
        config = ResourceConfig(
            scheme=self.payment_scheme,
            payTo=str(quote["recipient_address"]),
            price=AssetAmount(
                amount=str(amount_atomic),
                asset=SOLANA_DEVNET_USDC_MINT,
            ),
            network=self.network,
            maxTimeoutSeconds=self._remaining_timeout(quote),
        )
        requirements = self._server.build_payment_requirements(config)
        if len(requirements) != 1:
            raise AdapterConfigurationError("unexpected_solana_requirement_count")
        return requirements[0]

    def _validated_amount(self, quote: dict[str, Any]) -> int:
        try:
            amount_atomic = int(quote["amount_atomic"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterConfigurationError("invalid_solana_quote_amount") from exc
        if amount_atomic < 1 or amount_atomic > self._max_amount_atomic:
            raise AdapterConfigurationError("solana_quote_amount_out_of_range")
        return amount_atomic

    def _resource_url(self, quote: dict[str, Any]) -> str:
        return (
            f"{self._gateway_public_base_url}/v1/invoke/"
            f"{quote['tool_call_id']}"
        )

    @staticmethod
    def _remaining_timeout(quote: dict[str, Any]) -> int:
        raw_expiry = str(quote["expires_at"]).replace("Z", "+00:00")
        expiry = datetime.fromisoformat(raw_expiry)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        raw_created = str(quote["created_at"]).replace("Z", "+00:00")
        created = datetime.fromisoformat(raw_created)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        remaining = int((expiry - datetime.now(UTC)).total_seconds())
        if remaining < 1:
            raise AdapterConfigurationError("solana_quote_expired")
        # Recreate the immutable requirement exactly on a retry. Using the
        # current remaining time would change maxTimeoutSeconds after signing.
        return max(1, min(int((expiry - created).total_seconds()), 300))
