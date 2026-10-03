"""Two-step paid invocation client for the PaxRelay gateway.

The SDK requests a quote and submits proof supplied by the caller. It does not
hold keys, sign transfers, or initiate a payment.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias
from uuid import UUID

import httpx
from pydantic import ValidationError

from paxrelay.client import _normalize_api_root, _raise_api_error
from paxrelay.exceptions import PaxRelayConnectionError, PaxRelayProtocolError
from paxrelay.models import (
    ApprovalPending,
    GatewayCallResult,
    PaymentChallenge,
)

GatewayStartResult: TypeAlias = (
    PaymentChallenge | GatewayCallResult | ApprovalPending
)


class AsyncPaxRelayGatewayClient:
    """Call paid services through the PaxRelay gateway.

    ``api_key`` must have the ``gateway:invoke`` scope and ``agent_id`` must
    identify an active agent belonging to that key's tenant. Payment proof is
    supplied by the caller after handling the returned requirement.
    """

    def __init__(
        self,
        *,
        api_key: str,
        agent_id: UUID | str,
        base_url: str = "http://localhost:8080",
        timeout: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key or any(
            not 33 <= ord(character) <= 126 for character in api_key
        ):
            raise ValueError("api_key must be a non-empty visible ASCII string.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        try:
            normalized_agent_id = str(UUID(str(agent_id)))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("agent_id must be a valid UUID.") from exc

        self._api_root = _normalize_api_root(base_url)
        self._api_key = api_key
        self._agent_id = normalized_agent_id
        self._owns_http_client = http_client is None
        self._http_client = (
            http_client
            if http_client is not None
            else httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        )

    async def invoke(
        self,
        *,
        capability: str,
        idempotency_key: str,
        arguments: Mapping[str, Any],
        constraints: Mapping[str, Any] | None = None,
    ) -> GatewayStartResult:
        """Request a quote or receive a replayed result/approval response.

        A new payable request returns :class:`PaymentChallenge`. If policy
        requires a person to approve it, the method returns
        :class:`ApprovalPending`. An idempotent replay of an already completed
        request returns :class:`GatewayCallResult`.
        """
        body: dict[str, Any] = {
            "capability": capability,
            "idempotency_key": idempotency_key,
            "arguments": dict(arguments),
        }
        if constraints is not None:
            body["constraints"] = dict(constraints)
        response = await self._send("POST", "invoke", json=body)

        if response.status_code not in {200, 202, 402}:
            _raise_api_error(response)
        payload = self._decode_object(response)
        try:
            if response.status_code == 402:
                return PaymentChallenge.model_validate(payload)
            if response.status_code == 202:
                return ApprovalPending.model_validate(payload)
            return GatewayCallResult.model_validate(payload)
        except ValidationError as exc:
            raise PaxRelayProtocolError(
                "PaxRelay gateway returned a response that did not match its contract."
            ) from exc

    async def submit_proof(
        self,
        tool_call_id: UUID | str,
        *,
        proof: str,
    ) -> GatewayCallResult:
        """Submit caller-produced proof and return the provider result/receipt."""
        try:
            normalized_call_id = str(UUID(str(tool_call_id)))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("tool_call_id must be a valid UUID.") from exc
        if not isinstance(proof, str) or not proof:
            raise ValueError("proof must be a non-empty string.")

        response = await self._send(
            "POST",
            f"invoke/{normalized_call_id}",
            json={"proof": proof},
        )
        if response.status_code != 200:
            _raise_api_error(response)
        payload = self._decode_object(response)
        try:
            return GatewayCallResult.model_validate(payload)
        except ValidationError as exc:
            raise PaxRelayProtocolError(
                "PaxRelay gateway returned a response that did not match its contract."
            ) from exc

    async def _send(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any],
    ) -> httpx.Response:
        try:
            return await self._http_client.request(
                method,
                f"{self._api_root}/{path.lstrip('/')}",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "X-Agent-Id": self._agent_id,
                },
                json=json,
                follow_redirects=False,
            )
        except httpx.RequestError as exc:
            raise PaxRelayConnectionError(
                "Could not reach the PaxRelay gateway "
                f"({type(exc).__name__})."
            ) from exc

    @staticmethod
    def _decode_object(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise PaxRelayProtocolError(
                "PaxRelay gateway returned a successful response that was not valid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise PaxRelayProtocolError(
                "PaxRelay gateway returned a response that was not a JSON object."
            )
        return payload

    async def aclose(self) -> None:
        """Close the HTTP connection pool if this client created it."""
        if self._owns_http_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> "AsyncPaxRelayGatewayClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.aclose()
