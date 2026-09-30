"""Policy evaluation for gateway requests (fail-closed)."""

from __future__ import annotations

from paxrelay_domain import (
    Policy,
    PolicyDecision,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
)
from paxrelay_policy import PolicyEvaluator


class PolicyGateError(Exception):
    """Raised when policy denies a request or pauses the agent."""

    def __init__(self, status_code: int, result: PolicyEvaluationResult) -> None:
        super().__init__(result.explanation)
        self.status_code = status_code
        self.result = result


def evaluate_request(
    *,
    request: PolicyEvaluationRequest,
    policy: Policy,
    evaluator: PolicyEvaluator,
) -> PolicyEvaluationResult:
    """Run the policy and map non-ALLOW outcomes to errors.

    - DENY / PAUSE_AGENT → 403
    - REQUIRE_APPROVAL → 202 (caller should poll an approval)
    """
    result = evaluator.evaluate(request, policy)
    if result.decision == PolicyDecision.ALLOW:
        return result
    status_code = (
        202 if result.decision == PolicyDecision.REQUIRE_APPROVAL else 403
    )
    raise PolicyGateError(status_code, result)
