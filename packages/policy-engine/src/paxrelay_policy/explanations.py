"""Human-readable explanation generator for policy decisions."""

from __future__ import annotations

from paxrelay_domain import PolicyDecision, PolicyEvaluationRequest, PolicyMode

_RULE_MESSAGES: dict[str, str] = {
    "agent_status": "Agent is not active.",
    "emergency_stop": "Emergency stop is active for this agent.",
    "session_validity": "Agent session is invalid or expired.",
    "capability_access": "Requested capability is not on the agent's allowlist.",
    "provider_access": "Provider is blocked or not on the agent's allowlist.",
    "currency_restrictions": "Payment currency is not permitted by policy.",
    "per_call_limit": "Payment exceeds the maximum per-call limit.",
    "daily_budget": "Payment would exceed the agent's daily budget.",
    "monthly_budget": "Payment would exceed the agent's monthly budget.",
    "provider_quality": "Provider does not meet the minimum quality thresholds.",
    "failure_and_drawdown": "Agent has exceeded the maximum consecutive failure count.",
    "approval_threshold": "Payment amount requires human approval.",
}


def build_explanation(
    decision: PolicyDecision,
    blocking_rule: str | None,
    mode: PolicyMode,
    request: PolicyEvaluationRequest,
) -> str:
    if decision == PolicyDecision.ALLOW:
        if mode == PolicyMode.OBSERVE and blocking_rule:
            return (
                f"Request is within policy (observe mode). "
                f"Rule '{blocking_rule}' would have blocked in enforce mode."
            )
        if mode == PolicyMode.WARN and blocking_rule:
            return (
                f"Request permitted with warning. "
                f"Rule '{blocking_rule}' triggered: "
                f"{_RULE_MESSAGES.get(blocking_rule, 'Policy rule triggered.')}"
            )
        return (
            f"Request is within policy. Capability '{request.capability}' "
            f"is approved for provider '{request.provider_id}'."
        )

    if decision == PolicyDecision.REQUIRE_APPROVAL:
        return (
            f"Payment of {request.amount} requires human approval "
            f"before execution can proceed."
        )

    if decision == PolicyDecision.PAUSE_AGENT:
        return (
            f"Agent '{request.agent_id}' has been paused. "
            f"{_RULE_MESSAGES.get(blocking_rule or '', 'Policy rule triggered.')}"
        )

    # DENY
    rule_msg = _RULE_MESSAGES.get(blocking_rule or "", "Policy rule triggered.")
    return f"Request denied. {rule_msg}"
