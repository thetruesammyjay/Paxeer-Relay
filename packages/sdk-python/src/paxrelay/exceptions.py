"""Exceptions raised by the PaxRelay Python SDK."""

from __future__ import annotations


class PaxRelayError(Exception):
    """Base class for errors returned or encountered by the SDK."""


class PaxRelayAPIError(PaxRelayError):
    """An API response with an unsuccessful HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str = "api_error",
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id


class AuthenticationError(PaxRelayAPIError):
    """The API key is missing, invalid, expired, or inactive."""


class PermissionDeniedError(PaxRelayAPIError):
    """The API key does not have the scope needed for this operation."""


class ResourceNotFoundError(PaxRelayAPIError):
    """The requested resource does not exist in the caller's tenant."""


class ConflictError(PaxRelayAPIError):
    """The requested change conflicts with existing resource state."""


class APIValidationError(PaxRelayAPIError):
    """The API rejected one or more request fields."""


class RateLimitError(PaxRelayAPIError):
    """The API key reached its request limit."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str = "rate_limited",
        request_id: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            code=code,
            request_id=request_id,
        )
        self.retry_after_seconds = retry_after_seconds


class PaxRelayConnectionError(PaxRelayError):
    """The SDK could not complete an HTTP request to the API."""


class PaxRelayProtocolError(PaxRelayError):
    """The API returned a successful response that violated its JSON contract."""
