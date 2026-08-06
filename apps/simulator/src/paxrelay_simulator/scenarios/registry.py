"""Scenario registry for simulator test flows."""

from __future__ import annotations

# Each scenario is a coroutine that exercises one end-to-end flow against the
# local simulator.  Add scenarios here as async functions and wire them into
# the CLI runner in main.py when needed.

SCENARIOS: dict[str, str] = {
    "happy_path": "Successful single-call payment flow",
    "payment_expired": "Quote expires before the agent submits a proof",
    "provider_timeout": "Provider endpoint times out during forwarding",
    "policy_denied": "Agent policy blocks the capability",
    "duplicate_idempotency": "Replayed request returns cached result",
}
