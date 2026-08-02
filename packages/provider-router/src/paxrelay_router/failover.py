"""Failover logic — retryable condition classification and attempt tracking."""

from __future__ import annotations

from paxrelay_domain import ExecutionState

# Conditions under which a failover to another provider is permitted
RETRYABLE_STATES = {
    ExecutionState.TIMEOUT,
    ExecutionState.UNKNOWN,
}

# Conditions under which we must NOT retry (charge already happened or request is malformed)
NON_RETRYABLE_STATES = {
    ExecutionState.SUCCEEDED,
    ExecutionState.PROVIDER_ERROR,  # Provider accepted and completed (may have side effects)
    ExecutionState.CANCELLED,
}

# HTTP status codes that indicate a transient failure safe to retry
RETRYABLE_HTTP_CODES = {429, 502, 503, 504}


def is_retryable(
    execution_state: ExecutionState,
    http_status_code: int | None = None,
    payment_verified: bool = False,
) -> bool:
    """Return True if the attempt can safely be retried with another provider.

    A request MUST NOT be retried if:
    - The policy denied it
    - The payment proof was invalid
    - The provider accepted the request and completed side effects
    - The request itself was malformed

    A request MAY be retried if:
    - The connection failed before the provider received it
    - The provider timed out before accepting
    - The provider returned an explicit temporary-unavailable response
    """
    if execution_state in NON_RETRYABLE_STATES:
        return False
    if execution_state in RETRYABLE_STATES:
        return True
    if http_status_code in RETRYABLE_HTTP_CODES:
        return True
    return False


def can_failover(
    attempt_number: int,
    max_provider_attempts: int = 2,
    policy_allows: bool = True,
    payment_supports_retry: bool = True,
    idempotency_safe: bool = True,
) -> bool:
    """Return True if the router may select a different provider and retry."""
    if attempt_number >= max_provider_attempts:
        return False
    if not policy_allows:
        return False
    if not payment_supports_retry:
        return False
    if not idempotency_safe:
        return False
    return True
