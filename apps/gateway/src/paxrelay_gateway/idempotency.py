"""Idempotency — the unique (agent_id, idempotency_key) replay guard.

Repeating a request with the same idempotency key must return the previously
completed result instead of creating a second payment or execution.
"""

from __future__ import annotations

from paxrelay_domain import RequestState, ToolCall

# Terminal states after which a replayed request returns the stored result.
_REPLAYABLE_STATES = {
    RequestState.DELIVERED,
    RequestState.FAILED,
    RequestState.CANCELLED,
}


def is_replayable(call: ToolCall | None) -> bool:
    """Return True if the call is a previously-completed one to replay."""
    return call is not None and call.request_state in _REPLAYABLE_STATES
