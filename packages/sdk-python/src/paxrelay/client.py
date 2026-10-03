"""Async client for PaxRelay's tenant-scoped control-plane API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from paxrelay.exceptions import (
    APIValidationError,
    AuthenticationError,
    ConflictError,
    PaxRelayAPIError,
    PaxRelayConnectionError,
    PaxRelayProtocolError,
    PermissionDeniedError,
    RateLimitError,
    ResourceNotFoundError,
)


class AsyncPaxRelayClient:
    """Async entry point for tenant control-plane operations.

    ``base_url`` accepts the API origin, such as ``http://localhost:8000``,
    or an origin that already ends in ``/v1``. The client adds the bearer API
    key to each request. It owns and closes the HTTP connection pool unless an
    ``httpx.AsyncClient`` is supplied by the caller.

    The API key must have the scopes required by the operation. For example,
    creating an agent requires ``agents:write`` and listing agents requires
    ``agents:read``. Reading approvals requires ``approvals:read`` and recording
    decisions requires ``approvals:write``.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key or any(
            not 33 <= ord(character) <= 126 for character in api_key
        ):
            raise ValueError("api_key must be a non-empty visible ASCII string.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self._api_root = _normalize_api_root(base_url)
        self._api_key = api_key
        self._owns_http_client = http_client is None
        self._http_client = (
            http_client
            if http_client is not None
            else httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        )

        from paxrelay.agents import AgentsResource
        from paxrelay.approvals import ApprovalsResource
        from paxrelay.policies import PoliciesResource
        from paxrelay.providers import ProvidersResource
        from paxrelay.services import ServicesResource

        self.agents = AgentsResource(self)
        self.approvals = ApprovalsResource(self)
        self.policies = PoliciesResource(self)
        self.providers = ProvidersResource(self)
        self.services = ServicesResource(self)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        """Send one control-plane request and decode its JSON response."""
        url = f"{self._api_root}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        try:
            response = await self._http_client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                follow_redirects=False,
            )
        except httpx.RequestError as exc:
            raise PaxRelayConnectionError(
                f"Could not reach the PaxRelay API ({type(exc).__name__})."
            ) from exc

        if not response.is_success:
            _raise_api_error(response)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise PaxRelayProtocolError(
                "PaxRelay API returned a successful response that was not valid JSON."
            ) from exc

    async def aclose(self) -> None:
        """Close the HTTP connection pool if this client created it."""
        if self._owns_http_client:
            await self._http_client.aclose()

    @staticmethod
    def _path_id(resource_id: UUID | str) -> str:
        """Validate and normalize a resource identifier before using it in a URL."""
        try:
            return str(UUID(str(resource_id)))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("resource ID must be a valid UUID.") from exc

    async def __aenter__(self) -> "AsyncPaxRelayClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.aclose()


def _normalize_api_root(base_url: str) -> str:
    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
        _ = parsed.port
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("base_url must be an HTTP or HTTPS API origin.") from exc

    path = parsed.path.rstrip("/")
    local_http = (
        parsed.scheme == "http"
        and hostname is not None
        and hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    )
    if (
        (parsed.scheme != "https" and not local_http)
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or path not in {"", "/v1"}
    ):
        raise ValueError(
            "base_url must be an HTTP or HTTPS API origin, optionally ending in /v1."
        )

    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin + (path or "/v1")


def _raise_api_error(response: httpx.Response) -> None:
    status_code = response.status_code
    request_id = response.headers.get("X-Request-ID")
    code = "api_error"
    message = f"PaxRelay API returned HTTP {status_code}."
    try:
        body = response.json()
    except ValueError:
        body = None

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            if isinstance(error.get("code"), str):
                code = error["code"]
            if isinstance(error.get("message"), str):
                message = error["message"]

    error_args = {
        "message": message,
        "status_code": status_code,
        "code": code,
        "request_id": request_id,
    }
    exception_type: type[PaxRelayAPIError] = {
        401: AuthenticationError,
        403: PermissionDeniedError,
        404: ResourceNotFoundError,
        409: ConflictError,
        422: APIValidationError,
    }.get(status_code, PaxRelayAPIError)

    if status_code == 429:
        try:
            retry_after = int(response.headers["Retry-After"])
        except (KeyError, ValueError):
            retry_after = None
        raise RateLimitError(**error_args, retry_after_seconds=retry_after)
    raise exception_type(**error_args)
