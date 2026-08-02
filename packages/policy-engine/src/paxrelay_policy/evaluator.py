"""Deterministic, stateless policy evaluator.

The evaluator runs rules in strict order and returns a full
PolicyEvaluationResult with matched rules and a human-readable explanation.
"""

from __future__ import annotations

from paxrelay_domain import (
    Policy,
    PolicyDecision,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyMode,
)
from paxrelay_policy.rules import RULE_SEQUENCE
from paxrelay_policy.explanations import build_explanation


class PolicyEvaluator:
    """Evaluates a payment request against a versioned policy.

    Respects the policy mode:
    - OBSERVE: always returns ALLOW but records matched rules
    - WARN:    returns ALLOW but emits violation metadata
    - ENFORCE: blocks on first failing rule (production mode)
    """

    def evaluate(
        self,
        request: PolicyEvaluationRequest,
        policy: Policy,
    ) -> PolicyEvaluationResult:
        matched_rules: list[str] = []
        blocking_decision: PolicyDecision | None = None
        blocking_rule: str | None = None

        for rule_name, rule_fn in RULE_SEQUENCE:
            decision = rule_fn(request, policy.rules)
            if decision is not None and decision != PolicyDecision.ALLOW:
                matched_rules.append(rule_name)
                if blocking_decision is None:
                    blocking_decision = decision
                    blocking_rule = rule_name
                # In enforce mode stop immediately at first block
                if policy.mode == PolicyMode.ENFORCE:
                    break
            else:
                matched_rules.append(rule_name)

        # Determine final decision based on mode
        if blocking_decision is not None:
            if policy.mode == PolicyMode.OBSERVE:
                final_decision = PolicyDecision.ALLOW
            elif policy.mode == PolicyMode.WARN:
                final_decision = PolicyDecision.ALLOW  # Permit but upstream logs warning
            else:
                final_decision = blocking_decision
        else:
            final_decision = PolicyDecision.ALLOW

        # Only keep rules that actually fired (matched / caused decision)
        triggered = [r for r in matched_rules if r == blocking_rule] if blocking_decision else []
        passed = [r for r in matched_rules if r != blocking_rule]

        explanation = build_explanation(
            decision=final_decision,
            blocking_rule=blocking_rule,
            mode=policy.mode,
            request=request,
        )

        return PolicyEvaluationResult(
            decision=final_decision,
            matched_rules=triggered or passed[:3],  # Surface most relevant rules
            explanation=explanation,
            policy_version=policy.version,
            policy_id=policy.id,
            mode=policy.mode,
        )
