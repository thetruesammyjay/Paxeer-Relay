"""Policy rule implementations — one function per rule, in evaluation order.

Each rule function takes the evaluation context and active policy rules,
and returns a PolicyDecision if it should block/escalate, or None to pass.
Rules run in strict order; the first non-None result stops evaluation.
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paxrelay_domain import (
        PolicyDecision,
        PolicyEvaluationRequest,
        PolicyRules,
    )

from paxrelay_domain import PolicyDecision


def rule_agent_status(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """1. Agent must be active."""
    if req.agent_status != "active":
        return PolicyDecision.DENY
    return None


def rule_emergency_stop(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """2. Emergency stop flag halts all agent activity."""
    if req.emergency_stop:
        return PolicyDecision.PAUSE_AGENT
    return None


def rule_session_validity(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """3. Session must be valid."""
    if not req.session_valid:
        return PolicyDecision.DENY
    return None


def rule_capability_access(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """4. Capability must match the allowed list (supports glob patterns)."""
    if not rules.allowed_capabilities:
        return None  # Empty list = all capabilities allowed
    for pattern in rules.allowed_capabilities:
        if fnmatch.fnmatch(req.capability, pattern):
            return None
    return PolicyDecision.DENY


def rule_provider_access(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """5. Provider must not be on the blocklist and must be on allowlist if set."""
    if req.provider_id in rules.blocked_providers:
        return PolicyDecision.DENY
    if rules.allowed_providers and req.provider_id not in rules.allowed_providers:
        return PolicyDecision.DENY
    return None


def rule_currency_restrictions(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """6. Currency must be in the allowed list (if set)."""
    if not rules.allowed_currencies:
        return None
    if req.amount.currency.value not in rules.allowed_currencies:
        return PolicyDecision.DENY
    return None


def rule_per_call_limit(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """7. Single payment must not exceed the per-call limit."""
    if rules.maximum_per_call and req.amount > rules.maximum_per_call:
        return PolicyDecision.DENY
    return None


def rule_daily_budget(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """8. Daily spend + this payment must not exceed the daily budget."""
    if rules.daily_budget is None:
        return None
    projected = req.current_daily_spend + req.amount
    if projected > rules.daily_budget:
        return PolicyDecision.DENY
    return None


def rule_monthly_budget(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """9. Monthly spend + this payment must not exceed the monthly budget."""
    if rules.monthly_budget is None:
        return None
    projected = req.current_monthly_spend + req.amount
    if projected > rules.monthly_budget:
        return PolicyDecision.DENY
    return None


def rule_provider_quality(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """10. Provider must meet minimum reputation and success rate thresholds."""
    if (
        rules.minimum_provider_reputation is not None
        and req.provider_reputation < rules.minimum_provider_reputation
    ):
        return PolicyDecision.DENY
    if (
        rules.minimum_provider_success_rate is not None
        and req.provider_success_rate < rules.minimum_provider_success_rate
    ):
        return PolicyDecision.DENY
    if (
        rules.maximum_accepted_latency_ms is not None
        and req.provider_avg_latency_ms > rules.maximum_accepted_latency_ms
    ):
        return PolicyDecision.DENY
    return None


def rule_failure_limits(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """11. Pause agent if it has exceeded consecutive failure threshold."""
    if (
        rules.maximum_consecutive_failures is not None
        and req.consecutive_failures >= rules.maximum_consecutive_failures
    ):
        return PolicyDecision.PAUSE_AGENT
    return None


def rule_approval_threshold(
    req: "PolicyEvaluationRequest",
    rules: "PolicyRules",
) -> PolicyDecision | None:
    """12. Payments at or above the threshold require human approval."""
    if (
        rules.approval_threshold is not None
        and req.amount >= rules.approval_threshold
    ):
        return PolicyDecision.REQUIRE_APPROVAL
    return None


# Ordered evaluation sequence — matches README exactly
RULE_SEQUENCE = [
    ("agent_status", rule_agent_status),
    ("emergency_stop", rule_emergency_stop),
    ("session_validity", rule_session_validity),
    ("capability_access", rule_capability_access),
    ("provider_access", rule_provider_access),
    ("currency_restrictions", rule_currency_restrictions),
    ("per_call_limit", rule_per_call_limit),
    ("daily_budget", rule_daily_budget),
    ("monthly_budget", rule_monthly_budget),
    ("provider_quality", rule_provider_quality),
    ("failure_and_drawdown", rule_failure_limits),
    ("approval_threshold", rule_approval_threshold),
]
