"""Paid-tool orchestration for MCP hosts and agent applications."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from jsonschema import ValidationError as JsonSchemaValidationError
from paxrelay.exceptions import PaxRelayAPIError, PaxRelayError
from paxrelay.models import ApprovalPending, GatewayCallResult, PaymentChallenge
from paxrelay.payments import AsyncPaxRelayGatewayClient

from paxrelay_mcp.types import (
    MCPToolOutcome,
    PaidToolDefinition,
    PaymentProofProvider,
    validate_tool_arguments,
)


class PaxRelayMCPAdapter:
    """Run configured MCP tools through the paid PaxRelay gateway.

    The adapter never handles wallet secrets. A host can supply an async proof
    provider, or receive the payment requirement and complete it in its own
    wallet flow before calling :meth:`submit_proof`.
    """

    def __init__(
        self,
        gateway: AsyncPaxRelayGatewayClient,
        *,
        payment_proof_provider: PaymentProofProvider | None = None,
    ) -> None:
        self._gateway = gateway
        self._payment_proof_provider = payment_proof_provider

    async def call_tool(
        self,
        tool: PaidToolDefinition,
        *,
        arguments: Mapping[str, Any],
        idempotency_key: str,
    ) -> MCPToolOutcome:
        """Request a quote and, when configured, submit caller-produced proof.

        The idempotency key must be reused if the host retries the same
        invocation after an uncertain network outcome.
        """
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("idempotency_key must contain 1 to 128 characters.")
        try:
            validate_tool_arguments(tool, arguments)
        except JsonSchemaValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path) or "arguments"
            return MCPToolOutcome(
                status="invalid_arguments",
                idempotency_key=idempotency_key,
                error={
                    "code": "invalid_arguments",
                    "message": f"Arguments do not match the tool schema at {location}.",
                },
            )

        try:
            start = await self._gateway.invoke(
                capability=tool.capability,
                idempotency_key=idempotency_key,
                arguments=arguments,
                constraints=tool.constraints or None,
            )
        except PaxRelayError as exc:
            return _error_outcome(exc, idempotency_key=idempotency_key)

        if isinstance(start, ApprovalPending):
            return MCPToolOutcome(
                status="approval_pending",
                idempotency_key=idempotency_key,
                tool_call_id=None,
                approval=start.model_dump(mode="json"),
            )
        if isinstance(start, GatewayCallResult):
            return MCPToolOutcome(
                status="succeeded",
                idempotency_key=idempotency_key,
                result=start.result,
                receipt=start.receipt,
                replayed=start.replayed,
            )
        if not isinstance(start, PaymentChallenge):
            return MCPToolOutcome(
                status="gateway_error",
                idempotency_key=idempotency_key,
                error={
                    "code": "unexpected_gateway_response",
                    "message": "The gateway returned an unsupported response.",
                },
            )

        if self._payment_proof_provider is None:
            return _payment_required(start, idempotency_key)

        try:
            proof = await self._payment_proof_provider(tool=tool, challenge=start)
        except PaxRelayError as exc:
            return _error_outcome(
                exc,
                idempotency_key=idempotency_key,
                tool_call_id=start.tool_call_id,
            )
        except Exception:
            return MCPToolOutcome(
                status="payment_error",
                idempotency_key=idempotency_key,
                tool_call_id=start.tool_call_id,
                error={
                    "code": "payment_proof_unavailable",
                    "message": "The configured payment flow did not return proof.",
                },
            )
        if not isinstance(proof, str) or not proof:
            return MCPToolOutcome(
                status="payment_error",
                idempotency_key=idempotency_key,
                tool_call_id=start.tool_call_id,
                error={
                    "code": "invalid_payment_proof",
                    "message": "The configured payment flow returned invalid proof.",
                },
            )
        return await self.submit_proof(
            start.tool_call_id,
            proof=proof,
            idempotency_key=idempotency_key,
        )

    async def submit_proof(
        self,
        tool_call_id: UUID | str,
        *,
        proof: str,
        idempotency_key: str | None = None,
    ) -> MCPToolOutcome:
        """Complete a previously challenged call using caller-produced proof."""
        try:
            result = await self._gateway.submit_proof(tool_call_id, proof=proof)
        except PaxRelayError as exc:
            normalized_id: UUID | None
            try:
                normalized_id = UUID(str(tool_call_id))
            except ValueError:
                normalized_id = None
            return _error_outcome(
                exc,
                idempotency_key=idempotency_key,
                tool_call_id=normalized_id,
            )
        return MCPToolOutcome(
            status="succeeded",
            idempotency_key=idempotency_key,
            tool_call_id=UUID(str(tool_call_id)),
            result=result.result,
            receipt=result.receipt,
            replayed=result.replayed,
        )


def _payment_required(
    challenge: PaymentChallenge,
    idempotency_key: str,
) -> MCPToolOutcome:
    return MCPToolOutcome(
        status="payment_required",
        idempotency_key=idempotency_key,
        tool_call_id=challenge.tool_call_id,
        payment_requirement=challenge.payment_requirement.model_dump(mode="json"),
    )


def _error_outcome(
    error: PaxRelayError,
    *,
    idempotency_key: str | None,
    tool_call_id: UUID | None = None,
) -> MCPToolOutcome:
    if isinstance(error, PaxRelayAPIError):
        code = error.code
        message = error.message
        status_code = error.status_code
        if code == "provider_error":
            status = "provider_error"
        elif "payment" in code or status_code == 402:
            status = "payment_error"
        else:
            status = "gateway_error"
    else:
        code = "gateway_unavailable"
        message = "The gateway request did not complete. Retry with the same idempotency key."
        status_code = None
        status = "gateway_error"
    return MCPToolOutcome(
        status=status,
        idempotency_key=idempotency_key,
        tool_call_id=tool_call_id,
        error={"code": code, "message": message, "http_status": status_code},
    )
