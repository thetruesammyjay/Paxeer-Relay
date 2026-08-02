"""Orchestration service for the paid-call lifecycle.

Implements the README's sequence diagram: idempotency check → route → policy →
quote → 402 challenge → verify proof → forward → signed receipt.

Routing runs before policy so the policy engine sees the real per-call price and
the selected provider's reputation/latency/success-rate. All mutations happen
through the repository layer on the caller-provided ``AsyncSession`` so the
surrounding transaction commits/rolls back atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import (
    Agent,
    ExecutionAttempt,
    ExecutionState,
    MonetaryAmount,
    Payment,
    PaymentIntent,
    PaymentState,
    PolicyDecision,
    PolicyEvaluationRequest,
    PolicyEvaluator,
    RequestState,
    RouteConstraints,
    RouteRequest,
    ToolCall,
)
from paxrelay_db.repositories import (
    SqlAlchemyPaymentRepository,
    SqlAlchemyPolicyRepository,
    SqlAlchemyProviderRepository,
    SqlAlchemyReceiptRepository,
    SqlAlchemyRouteRepository,
    SqlAlchemyToolCallRepository,
)
from paxrelay_receipts import hash_body
from paxrelay_router import ProviderRouter

from paxrelay_gateway.payment.quotes import build_quote, quote_to_requirement_input
from paxrelay_gateway.policy.service import PolicyGateError, evaluate_request
from paxrelay_gateway.proxy.forwarder import forward_request
from paxrelay_gateway.receipts.issuer import build_and_sign_receipt
from paxrelay_gateway.verification import VerificationError, verify_payment_proof


class PaymentAdapter(Protocol):
    """The slice of the Paxeer adapter the invoke service needs."""

    async def create_payment_requirement(self, quote: dict) -> dict: ...

    async def verify_payment(self, proof: str, quote: dict) -> dict: ...


@dataclass
class QuoteResult:
    """Outcome of the first (challenge) phase of a paid call."""

    status_code: int
    body: dict[str, Any]
    tool_call_id: UUID | None = None


@dataclass
class InvokeResult:
    """Outcome of the second (verification + forwarding) phase."""

    status_code: int
    body: dict[str, Any]
    tool_call_id: UUID | None = None


class GatewayInvokeService:
    """Coordinates a single paid tool call through its full lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        paxeer: PaymentAdapter,
        router: ProviderRouter,
        evaluator: PolicyEvaluator,
        signer: Any,
        quote_ttl_seconds: int = 300,
        max_provider_attempts: int = 2,
    ) -> None:
        self._session = session
        self._paxeer = paxeer
        self._router = router
        self._evaluator = evaluator
        self._signer = signer
        self._quote_ttl_seconds = quote_ttl_seconds
        self._max_provider_attempts = max_provider_attempts

    # ------------------------------------------------------------------
    # Phase 1 — request intake and the 402 challenge
    # ------------------------------------------------------------------

    async def start(
        self,
        *,
        agent: Agent,
        capability: str,
        idempotency_key: str,
        arguments: dict[str, Any],
        constraints: dict[str, Any] | None = None,
    ) -> QuoteResult:
        """Handle a new invocation: idempotency → route → policy → 402 quote."""
        tool_calls = SqlAlchemyToolCallRepository(self._session)

        # 1. Idempotency — a completed prior request replays its result.
        existing = await tool_calls.get_by_idempotency_key(agent.id, idempotency_key)
        if existing is not None and existing.request_state == RequestState.DELIVERED:
            return QuoteResult(
                status_code=200,
                body={"replayed": True, "tool_call_id": str(existing.id)},
                tool_call_id=existing.id,
            )

        # 2. Persist the tool call (state: CREATED) with a stable request hash.
        request_hash = hash_body(_canonical_args(arguments))
        call = ToolCall(
            id=uuid4(),
            agent_id=agent.id,
            organisation_id=agent.organisation_id,
            project_id=agent.project_id,
            capability=capability,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            arguments=arguments,
            constraints=constraints or {},
        )
        await tool_calls.save(call)

        # 3. Route — pick the provider (needed before policy for the real price).
        providers = SqlAlchemyProviderRepository(self._session)
        candidates = await providers.find_eligible_services(
            capability, agent.organisation_id, agent.project_id
        )
        if not candidates:
            return QuoteResult(
                status_code=503,
                body=_err("no_eligible_provider", "No provider offers this capability."),
                tool_call_id=call.id,
            )
        route_request = RouteRequest(
            capability=capability,
            constraints=RouteConstraints(**constraints) if constraints else RouteConstraints(),
        )
        route = self._router.select(route_request, candidates, tool_call_id=call.id)
        if route is None:
            return QuoteResult(
                status_code=503,
                body=_err("routing_failed", "No provider passed routing filters."),
                tool_call_id=call.id,
            )
        await SqlAlchemyRouteRepository(self._session).save(route)

        # Resolve the winning candidate's price and metrics for policy input.
        chosen = _find_candidate(candidates, route.service_version_id)
        best_svc, _best_ver, best_metrics = chosen
        price = best_svc.pricing.price_per_call or MonetaryAmount.zero()

        provider = await providers.get(route.provider_id)
        recipient = (provider.wallet_address if provider else None) or _ZERO_ADDRESS

        # 4. Policy evaluation with the real amount and provider metrics.
        policy_repo = SqlAlchemyPolicyRepository(self._session)
        policy = await policy_repo.get_active_for_agent(agent.id)
        if policy is None:
            return QuoteResult(
                status_code=403,
                body=_err("no_policy", "Agent has no active policy assigned."),
                tool_call_id=call.id,
            )
        daily = await policy_repo.get_daily_spend(agent.id)
        monthly = await policy_repo.get_monthly_spend(agent.id)
        req = PolicyEvaluationRequest(
            agent_id=str(agent.id),
            capability=capability,
            provider_id=str(route.provider_id),
            amount=price,
            current_daily_spend=MonetaryAmount(amount_atomic=daily),
            current_monthly_spend=MonetaryAmount(amount_atomic=monthly),
            provider_reputation=best_metrics.reputation_score,
            provider_success_rate=best_metrics.success_rate,
            provider_avg_latency_ms=best_metrics.avg_latency_ms,
            agent_status=agent.status.value,
        )
        try:
            evaluate_request(request=req, policy=policy, evaluator=self._evaluator)
        except PolicyGateError as exc:
            return QuoteResult(
                status_code=exc.status_code,
                body={
                    "decision": exc.result.decision.value,
                    "explanation": exc.result.explanation,
                },
                tool_call_id=call.id,
            )

        # 5. Build the quote and return the 402 challenge.
        quote = build_quote(
            tool_call_id=call.id,
            provider_id=route.provider_id,
            service_version_id=route.service_version_id,
            amount=price,
            recipient_address=recipient,
            request_hash=request_hash,
            ttl_seconds=self._quote_ttl_seconds,
        )
        await SqlAlchemyPaymentRepository(self._session).save_quote(quote)

        requirement = await self._paxeer.create_payment_requirement(
            quote_to_requirement_input(quote)
        )
        return QuoteResult(
            status_code=402,
            body={"payment_requirement": requirement, "tool_call_id": str(call.id)},
            tool_call_id=call.id,
        )

    # ------------------------------------------------------------------
    # Phase 2 — proof submission, verification, forwarding, receipt
    # ------------------------------------------------------------------

    async def complete(
        self,
        *,
        tool_call_id: UUID,
        proof: str,
        client: Any = None,
    ) -> InvokeResult:
        """Verify the proof, forward the request, and issue the receipt."""
        tool_calls = SqlAlchemyToolCallRepository(self._session)
        payments = SqlAlchemyPaymentRepository(self._session)

        call = await tool_calls.get(tool_call_id)
        if call is None:
            return InvokeResult(status_code=404, body=_err("not_found", "tool_call_not_found"))
        if call.request_state == RequestState.DELIVERED:
            return InvokeResult(
                status_code=200,
                body={"replayed": True, "tool_call_id": str(call.id)},
                tool_call_id=call.id,
            )

        quote = await payments.get_quote_by_tool_call(call.id)
        if quote is None:
            return InvokeResult(status_code=404, body=_err("not_found", "quote_not_found"))

        # 1. Verify the proof (local checklist + adapter, fail-closed).
        try:
            verification = await verify_payment_proof(
                proof=proof, quote=quote, adapter=self._paxeer
            )
        except VerificationError as exc:
            return InvokeResult(
                status_code=402,
                body=_err("payment_not_verified", exc.reason),
                tool_call_id=call.id,
            )

        # 2. Record intent + verified payment, and consume the nonce.
        intent = PaymentIntent(
            id=uuid4(),
            tool_call_id=call.id,
            quote_id=quote.id,
            agent_id=call.agent_id,
            provider_id=quote.provider_id,
            amount=quote.amount,
        )
        await payments.save_intent(intent)
        payment = Payment(
            id=uuid4(),
            intent_id=intent.id,
            tool_call_id=call.id,
            quote_id=quote.id,
            agent_id=call.agent_id,
            provider_id=quote.provider_id,
            amount=quote.amount,
            state=PaymentState.VERIFIED,
            proof=proof,
            layerx_transaction_hash=verification.get("layerx_transaction_hash"),
            layerx_batch_id=verification.get("layerx_batch_id"),
            verified_at=datetime.utcnow(),
        )
        await payments.save(payment)
        await payments.mark_nonce_used(quote.nonce, payment.id)

        call = call.model_copy(
            update={
                "request_state": RequestState.PAYMENT_VERIFIED,
                "payment_state": PaymentState.VERIFIED,
            }
        )
        await tool_calls.save(call)

        # 3. Forward the authorised request to the provider.
        providers = SqlAlchemyProviderRepository(self._session)
        version = await providers.get_service_version(quote.service_version_id)
        if version is None:
            return InvokeResult(
                status_code=503,
                body=_err("service_version_missing", "Service version not found."),
                tool_call_id=call.id,
            )

        attempt = ExecutionAttempt(
            id=uuid4(),
            tool_call_id=call.id,
            payment_id=payment.id,
            provider_id=quote.provider_id,
            service_version_id=quote.service_version_id,
            attempt_number=1,
        )
        await tool_calls.save_attempt(attempt)

        forward = await forward_request(
            endpoint_url=version.endpoint_url,
            arguments=call.arguments,
            timeout_seconds=version.delivery.timeout_seconds,
            client=client,
        )
        attempt = attempt.model_copy(
            update={
                "execution_state": forward.execution_state,
                "request_forwarded_at": forward.started_at,
                "response_received_at": forward.completed_at,
                "latency_ms": forward.latency_ms,
                "http_status_code": forward.http_status_code,
                "is_retryable": forward.execution_state
                in (ExecutionState.TIMEOUT, ExecutionState.UNKNOWN),
            }
        )
        await tool_calls.save_attempt(attempt)

        if forward.execution_state != ExecutionState.SUCCEEDED:
            call = call.model_copy(update={"request_state": RequestState.FAILED})
            await tool_calls.save(call)
            return InvokeResult(
                status_code=502,
                body=_err("provider_error", forward.error_code or "provider_failed"),
                tool_call_id=call.id,
            )

        # 4. Generate and sign the execution receipt.
        route = await SqlAlchemyRouteRepository(self._session).get_by_tool_call(call.id)
        receipt = build_and_sign_receipt(
            tool_call_id=call.id,
            agent_id=call.agent_id,
            provider_id=quote.provider_id,
            service_id=version.service_id,
            service_version=version.version,
            capability=call.capability,
            request_hash=call.request_hash or hash_body(_canonical_args(call.arguments)),
            response_hash=hash_body(forward.response_bytes),
            amount=quote.amount,
            payment_id=payment.id,
            layerx_transaction_hash=payment.layerx_transaction_hash,
            route_id=route.id if route else uuid4(),
            strategy=route.strategy.value if route else "balanced",
            route_score=route.score if route else 0.0,
            execution_started_at=forward.started_at,
            execution_completed_at=forward.completed_at,
            latency_ms=forward.latency_ms,
            execution_status=forward.execution_state,
            signer=self._signer,
        )
        await SqlAlchemyReceiptRepository(self._session).save(receipt)

        call = call.model_copy(update={"request_state": RequestState.DELIVERED})
        await tool_calls.save(call)

        return InvokeResult(
            status_code=200,
            body={
                "result": forward.response_body,
                "receipt": receipt.model_dump(mode="json"),
            },
            tool_call_id=call.id,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ZERO_ADDRESS = "0x0000000000000000000000000000000000000001"


def _canonical_args(arguments: dict[str, Any]) -> bytes:
    """Stable byte encoding of arguments for hashing (sorted keys)."""
    import json

    return json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _find_candidate(candidates: list, service_version_id: UUID):
    """Return the (service, version, metrics) tuple for the chosen version."""
    for svc, ver, metrics in candidates:
        if ver.id == service_version_id:
            return svc, ver, metrics
    return candidates[0]
