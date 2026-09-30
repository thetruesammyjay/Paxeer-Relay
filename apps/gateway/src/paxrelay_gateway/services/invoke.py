"""Orchestration service for the paid-call lifecycle.

Implements the README's sequence diagram: idempotency check → route → policy →
quote → 402 challenge → verify proof → forward → signed receipt.

Routing runs before policy so the policy engine sees the real per-call price and
the selected provider's reputation/latency/success-rate. Mutations use the
caller-provided ``AsyncSession``. Payment verification and the execution
reservation have explicit commit boundaries before the provider network call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db.models.executions import ApprovalRequestModel
from paxrelay_db.repositories._common import sid
from paxrelay_domain import (
    Agent,
    ExecutionAttempt,
    ExecutionState,
    MonetaryAmount,
    ProviderMetrics,
    Payment,
    PaymentIntent,
    PaymentState,
    PolicyEvaluationRequest,
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
from paxrelay_policy import PolicyEvaluator
from paxrelay_router import ProviderRouter

from paxrelay_gateway.payment.quotes import build_quote, quote_to_requirement_input
from paxrelay_gateway.policy.service import PolicyGateError, evaluate_request
from paxrelay_gateway.proxy.endpoint_security import (
    ProviderEndpointResolutionTimeout,
    UnsafeProviderEndpoint,
    resolve_provider_endpoint,
)
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
        max_provider_response_bytes: int = 10_485_760,
        max_provider_timeout_seconds: int = 30,
        provider_connect_timeout_seconds: int = 5,
        allow_private_provider_endpoints: bool = False,
        allowed_provider_hosts: frozenset[str] | None = None,
        approval_ttl_seconds: int = 900,
        require_provider_wallet: bool = False,
    ) -> None:
        self._session = session
        self._paxeer = paxeer
        self._router = router
        self._evaluator = evaluator
        self._signer = signer
        self._quote_ttl_seconds = quote_ttl_seconds
        self._approval_ttl_seconds = approval_ttl_seconds
        self._max_provider_attempts = max_provider_attempts
        self._max_provider_response_bytes = max_provider_response_bytes
        self._max_provider_timeout_seconds = max_provider_timeout_seconds
        self._provider_connect_timeout_seconds = provider_connect_timeout_seconds
        self._allow_private_provider_endpoints = allow_private_provider_endpoints
        self._require_provider_wallet = require_provider_wallet
        self._allowed_provider_hosts = allowed_provider_hosts

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

        request_hash = hash_body(_canonical_args(arguments))
        normal_constraints = constraints or {}
        approval: ApprovalRequestModel | None = None
        call: ToolCall | None = None
        await tool_calls.lock_idempotency_key(agent.id, idempotency_key)
        existing = await tool_calls.get_by_idempotency_key(agent.id, idempotency_key)
        if existing is not None:
            if (
                existing.request_hash != request_hash
                or existing.capability != capability
                or existing.constraints != normal_constraints
            ):
                return QuoteResult(
                    status_code=409,
                    body=_err(
                        "idempotency_key_reused",
                        "This idempotency key belongs to a different request.",
                    ),
                    tool_call_id=existing.id,
                )
            if existing.request_state == RequestState.DELIVERED:
                return QuoteResult(
                    status_code=200,
                    body={"replayed": True, "tool_call_id": str(existing.id)},
                    tool_call_id=existing.id,
                )
            if existing.request_state == RequestState.PAYMENT_REQUIRED:
                payment_repo = SqlAlchemyPaymentRepository(self._session)
                quote = await payment_repo.get_quote_by_tool_call(existing.id)
                if quote is None:
                    return QuoteResult(
                        status_code=409,
                        body=_err(
                            "request_incomplete",
                            "The stored quote is unavailable.",
                        ),
                        tool_call_id=existing.id,
                    )
                if quote.is_expired():
                    return QuoteResult(
                        status_code=410,
                        body=_err(
                            "quote_expired",
                            "Use a new idempotency key to retry.",
                        ),
                        tool_call_id=existing.id,
                    )
                requirement = await self._paxeer.create_payment_requirement(
                    quote_to_requirement_input(quote)
                )
                return QuoteResult(
                    status_code=402,
                    body={
                        "payment_requirement": requirement,
                        "tool_call_id": str(existing.id),
                    },
                    tool_call_id=existing.id,
                )
            if existing.request_state == RequestState.APPROVAL_PENDING:
                approval_stmt = (
                    select(ApprovalRequestModel)
                    .where(
                        ApprovalRequestModel.tool_call_id == sid(existing.id),
                    )
                    .with_for_update()
                )
                approval = (
                    await self._session.execute(approval_stmt)
                ).scalar_one_or_none()
                if approval is None:
                    return QuoteResult(
                        status_code=409,
                        body=_err(
                            "approval_unavailable",
                            "The approval record for this request is unavailable.",
                        ),
                        tool_call_id=existing.id,
                    )
                now = datetime.utcnow()
                if (
                    approval.status in {"pending", "approved"}
                    and approval.expires_at is not None
                    and approval.expires_at <= now
                ):
                    approval.status = "expired"
                    existing = existing.model_copy(
                        update={"request_state": RequestState.EXPIRED}
                    )
                    await tool_calls.save(existing)
                    await self._session.flush()
                    return QuoteResult(
                        status_code=410,
                        body=_err("approval_expired", "The approval request expired."),
                        tool_call_id=existing.id,
                    )
                if approval.status == "pending":
                    return QuoteResult(
                        status_code=202,
                        body={
                            "status": "approval_pending",
                            "approval_id": str(approval.id),
                            "tool_call_id": str(existing.id),
                        },
                        tool_call_id=existing.id,
                    )
                if approval.status in {"rejected", "expired", "invalidated"}:
                    return QuoteResult(
                        status_code=409,
                        body=_err(
                            f"approval_{approval.status}",
                            f"The approval request was {approval.status}.",
                        ),
                        tool_call_id=existing.id,
                    )
                if approval.status != "approved":
                    return QuoteResult(
                        status_code=409,
                        body=_err(
                            "approval_not_actionable",
                            "The approval request cannot authorize a new quote.",
                        ),
                        tool_call_id=existing.id,
                    )
                call = existing
            if existing.request_state in {
                RequestState.FAILED,
                RequestState.EXPIRED,
                RequestState.CANCELLED,
            }:
                return QuoteResult(
                    status_code=409,
                    body=_err(
                        "idempotent_request_terminal",
                        f"This request is already {existing.request_state.value}.",
                    ),
                    tool_call_id=existing.id,
                )
            if call is None:
                return QuoteResult(
                    status_code=202,
                    body={
                        "status": existing.request_state.value,
                        "tool_call_id": str(existing.id),
                    },
                    tool_call_id=existing.id,
                )

        # 2. Persist the tool call (state: CREATED) with a stable request hash.
        if call is None:
            call = ToolCall(
                id=uuid4(),
                agent_id=agent.id,
                organisation_id=agent.organisation_id,
                project_id=agent.project_id,
                capability=capability,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                arguments=arguments,
                constraints=normal_constraints,
            )
            await tool_calls.save(call)

        # 3. Route — pick the provider (needed before policy for the real price).
        providers = SqlAlchemyProviderRepository(self._session)
        routes = SqlAlchemyRouteRepository(self._session)
        if approval is not None:
            route = await routes.get_by_tool_call(call.id)
            if (
                route is None
                or approval.provider_id is None
                or approval.service_version_id is None
                or approval.recipient_address is None
                or approval.request_hash != request_hash
                or sid(route.provider_id) != approval.provider_id
                or sid(route.service_version_id) != approval.service_version_id
            ):
                approval.status = "invalidated"
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
                return QuoteResult(
                    status_code=409,
                    body=_err(
                        "approval_snapshot_invalid",
                        "The approved route snapshot is incomplete or has changed.",
                    ),
                    tool_call_id=call.id,
                )
            best_svc = await providers.get_service(route.service_id)
            _best_ver = await providers.get_service_version(route.service_version_id)
            provider = await providers.get(route.provider_id)
            if (
                best_svc is None
                or _best_ver is None
                or provider is None
                or not provider.is_operable()
                or (self._require_provider_wallet and not provider.wallet_address)
                or best_svc.status.value != "active"
                or not _best_ver.is_active
                or _best_ver.provider_id != route.provider_id
                or best_svc.provider_id != route.provider_id
                or provider.organisation_id != agent.organisation_id
                or provider.project_id != agent.project_id
            ):
                approval.status = "invalidated"
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
                return QuoteResult(
                    status_code=409,
                    body=_err(
                        "approved_provider_unavailable",
                        "The approved provider or service is no longer available.",
                    ),
                    tool_call_id=call.id,
                )
            current_recipient = provider.wallet_address or _ZERO_ADDRESS
            if current_recipient.lower() != approval.recipient_address.lower():
                approval.status = "invalidated"
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
                return QuoteResult(
                    status_code=409,
                    body=_err(
                        "approved_recipient_changed",
                        "The provider payment destination changed after approval.",
                    ),
                    tool_call_id=call.id,
                )
            best_metrics = await providers.get_metrics(route.service_id) or ProviderMetrics(
                service_id=route.service_id,
                provider_id=route.provider_id,
            )
            price = MonetaryAmount(
                amount_atomic=int(approval.amount_atomic),
                currency=approval.currency,
                decimals=approval.currency_decimals,
            )
            version_price = _best_ver.pricing.price_per_call or MonetaryAmount.zero()
            if price != version_price:
                approval.status = "invalidated"
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
                return QuoteResult(
                    status_code=409,
                    body=_err(
                        "approved_price_changed",
                        "The approved price no longer matches the service version.",
                    ),
                    tool_call_id=call.id,
                )
            recipient = approval.recipient_address
        else:
            candidates = await providers.find_eligible_services(
                capability, agent.organisation_id, agent.project_id
            )
            if not candidates:
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
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
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
                return QuoteResult(
                    status_code=503,
                    body=_err("routing_failed", "No provider passed routing filters."),
                    tool_call_id=call.id,
                )
            best_svc, _best_ver, best_metrics = _find_candidate(
                candidates, route.service_version_id
            )
            await routes.save(route)
            provider = await providers.get(route.provider_id)
            if self._require_provider_wallet and (
                provider is None or not provider.wallet_address
            ):
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
                return QuoteResult(
                    status_code=503,
                    body=_err(
                        "provider_payment_destination_missing",
                        "The selected provider has no configured payment wallet.",
                    ),
                    tool_call_id=call.id,
                )
            recipient = (provider.wallet_address if provider else None) or _ZERO_ADDRESS
            price = _best_ver.pricing.price_per_call or MonetaryAmount.zero()

        # Reject unsafe destinations before issuing a payment challenge. The
        # forwarder resolves and pins the address again after payment so DNS
        # changes between quote and completion cannot change the destination.
        try:
            await resolve_provider_endpoint(
                _best_ver.endpoint_url,
                allow_private=self._allow_private_provider_endpoints,
                timeout_seconds=self._provider_connect_timeout_seconds,
                allowed_hosts=self._allowed_provider_hosts,
            )
        except (ProviderEndpointResolutionTimeout, UnsafeProviderEndpoint):
            if approval is None:
                call = call.model_copy(update={"request_state": RequestState.FAILED})
                await tool_calls.save(call)
            return QuoteResult(
                status_code=503,
                body=_err(
                    "provider_endpoint_unavailable",
                    "The selected provider endpoint is not available.",
                ),
                tool_call_id=call.id,
            )

        # 4. Policy evaluation with the real amount and provider metrics.
        policy_repo = SqlAlchemyPolicyRepository(self._session)
        policy = await policy_repo.get_active_for_agent(agent.id)
        if policy is None:
            if approval is not None:
                approval.status = "invalidated"
            call = call.model_copy(update={"request_state": RequestState.FAILED})
            await tool_calls.save(call)
            return QuoteResult(
                status_code=403,
                body=_err("no_policy", "Agent has no active policy assigned."),
                tool_call_id=call.id,
            )
        if approval is not None and (
            approval.policy_id != sid(policy.id)
            or approval.policy_version != policy.version
        ):
            approval.status = "invalidated"
            call = call.model_copy(update={"request_state": RequestState.FAILED})
            await tool_calls.save(call)
            return QuoteResult(
                status_code=409,
                body=_err(
                    "approval_policy_changed",
                    "The active policy changed after approval; request a new decision.",
                ),
                tool_call_id=call.id,
            )
        has_budget_limits = (
            policy.rules.daily_budget is not None
            or policy.rules.monthly_budget is not None
        )
        if has_budget_limits and not await policy_repo.lock_agent_for_budget(
            agent.id
        ):
            if approval is not None:
                approval.status = "invalidated"
            call = call.model_copy(update={"request_state": RequestState.FAILED})
            await tool_calls.save(call)
            return QuoteResult(
                status_code=403,
                body=_err("agent_unavailable", "Agent is not available."),
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
        policy_to_evaluate = policy
        if approval is not None:
            # Keep every current policy gate active and lift only the threshold
            # that the reviewer explicitly approved.
            policy_to_evaluate = policy.model_copy(
                update={
                    "rules": policy.rules.model_copy(
                        update={"approval_threshold": None}
                    )
                }
            )
        try:
            evaluate_request(
                request=req,
                policy=policy_to_evaluate,
                evaluator=self._evaluator,
            )
        except PolicyGateError as exc:
            if approval is not None:
                approval.status = "invalidated"
            next_state = (
                RequestState.APPROVAL_PENDING
                if exc.status_code == 202
                else RequestState.FAILED
            )
            call = call.model_copy(update={"request_state": next_state})
            await tool_calls.save(call)
            if exc.status_code == 202 and approval is None:
                approval = ApprovalRequestModel(
                    id=sid(uuid4()),
                    organisation_id=sid(agent.organisation_id),
                    project_id=sid(agent.project_id),
                    environment=agent.environment.value,
                    tool_call_id=sid(call.id),
                    agent_id=sid(agent.id),
                    amount_atomic=price.amount_atomic,
                    currency=price.currency.value,
                    currency_decimals=price.decimals,
                    capability=capability,
                    provider_id=sid(route.provider_id),
                    service_version_id=sid(route.service_version_id),
                    recipient_address=recipient,
                    request_hash=request_hash,
                    policy_id=sid(policy.id),
                    policy_version=policy.version,
                    status="pending",
                    reason=exc.result.explanation[:512],
                    expires_at=(
                        datetime.utcnow()
                        + timedelta(seconds=self._approval_ttl_seconds)
                    ),
                )
                self._session.add(approval)
                await self._session.flush()
            return QuoteResult(
                status_code=exc.status_code,
                body={
                    "decision": exc.result.decision.value,
                    "explanation": exc.result.explanation,
                    **(
                        {
                            "approval_id": approval.id,
                            "status": "approval_pending",
                            "expires_at": approval.expires_at.isoformat() + "Z",
                        }
                        if approval is not None
                        else {}
                    ),
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
        call = call.model_copy(
            update={
                "request_state": RequestState.PAYMENT_REQUIRED,
                "payment_state": PaymentState.QUOTED,
            }
        )
        await tool_calls.save(call)
        if has_budget_limits:
            await policy_repo.reserve_budget(agent, quote)
        if approval is not None:
            approval.status = "consumed"

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
        agent: Agent,
        proof: str,
        client: Any = None,
    ) -> InvokeResult:
        """Verify the proof, forward the request, and issue the receipt."""
        tool_calls = SqlAlchemyToolCallRepository(self._session)
        payments = SqlAlchemyPaymentRepository(self._session)

        call = await tool_calls.get(tool_call_id)
        if call is None:
            return InvokeResult(status_code=404, body=_err("not_found", "tool_call_not_found"))
        if (
            call.agent_id != agent.id
            or call.organisation_id != agent.organisation_id
            or call.project_id != agent.project_id
        ):
            # Do not reveal whether another agent's tool-call ID exists.
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

        if not await payments.consume_nonce(quote.id, quote.nonce, call.agent_id):
            return InvokeResult(
                status_code=409,
                body=_err(
                    "quote_already_used",
                    "This quote has already been submitted.",
                ),
                tool_call_id=call.id,
            )

        # 2. Consume the nonce and record the verified payment in one transaction.
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

        call = call.model_copy(
            update={
                "request_state": RequestState.PAYMENT_VERIFIED,
                "payment_state": PaymentState.VERIFIED,
            }
        )
        await tool_calls.save(call)

        # Payment verification has an external side effect. Persist the
        # single-use nonce and payment before making a provider request, so a
        # crash or provider failure cannot make this proof reusable.
        await self._session.commit()

        # 3. Forward the authorised request to the provider.
        providers = SqlAlchemyProviderRepository(self._session)
        version = await providers.get_service_version(quote.service_version_id)
        if version is None:
            call = call.model_copy(update={"request_state": RequestState.FAILED})
            await tool_calls.save(call)
            return InvokeResult(
                status_code=503,
                body=_err("service_version_missing", "Service version not found."),
                tool_call_id=call.id,
            )

        call = call.model_copy(
            update={
                "request_state": RequestState.EXECUTION_RESERVED,
                "execution_state": ExecutionState.RESERVED,
            }
        )
        await tool_calls.save(call)
        attempt = ExecutionAttempt(
            id=uuid4(),
            tool_call_id=call.id,
            payment_id=payment.id,
            provider_id=quote.provider_id,
            service_version_id=quote.service_version_id,
            attempt_number=1,
            execution_state=ExecutionState.RESERVED,
        )
        await tool_calls.save_attempt(attempt)
        # Persist the execution reservation before crossing the provider
        # network boundary. A crash afterward remains visible for reconciliation.
        await self._session.commit()

        forward = await forward_request(
            endpoint_url=version.endpoint_url,
            arguments=call.arguments,
            timeout_seconds=min(
                version.delivery.timeout_seconds,
                self._max_provider_timeout_seconds,
            ),
            connect_timeout_seconds=self._provider_connect_timeout_seconds,
            max_response_bytes=self._max_provider_response_bytes,
            allow_private_endpoints=self._allow_private_provider_endpoints,
            allowed_provider_hosts=self._allowed_provider_hosts,
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
            call = call.model_copy(
                update={
                    "request_state": RequestState.FAILED,
                    "execution_state": forward.execution_state,
                }
            )
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

        call = call.model_copy(
            update={
                "request_state": RequestState.DELIVERED,
                "execution_state": ExecutionState.SUCCEEDED,
            }
        )
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
