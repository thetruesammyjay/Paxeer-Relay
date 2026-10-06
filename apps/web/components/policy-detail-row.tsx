"use client";

import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { assignPolicy, usePolicy } from "@/hooks/use-policies";
import type { PolicySummary } from "@/hooks/use-policies";
import { ApiError } from "@/lib/api-client";

interface PolicyDetailRowProps {
  policy: PolicySummary;
  apiKey: string;
  connectionId: string;
}

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function formatMoney(amount: {
  amount_atomic: string | number;
  currency: string;
  decimals: number;
} | null) {
  if (!amount) return "Not set";
  try {
    const atomic = BigInt(amount.amount_atomic);
    const scale = 10n ** BigInt(amount.decimals);
    const whole = atomic / scale;
    const fraction = (atomic % scale).toString().padStart(amount.decimals, "0");
    return `${amount.currency} ${whole}.${fraction}`;
  } catch {
    return "Invalid amount returned by API";
  }
}

function formatRuleList(values: string[], emptyLabel: string) {
  return values.length ? values.join(", ") : emptyLabel;
}

function formatAssignedDate(value: string) {
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function assignmentErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) return "Your current project access needs policies:write permission to assign a policy.";
    if (error.status === 404) return "The agent was not found in this project and environment.";
    if (error.status === 409) return "This policy is already assigned to that agent.";
    if (error.status === 422) return "Enter a valid agent UUID.";
    return `Assignment failed (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function detailErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session expired or was rejected. Sign in again or reconnect your development key.";
    if (error.status === 403) return "Your current project access needs policies:read permission to inspect rule details.";
    if (error.status === 404) return "This policy is no longer available in the connected project.";
    return `Policy details could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

export function PolicyDetailRow({ policy, apiKey, connectionId }: PolicyDetailRowProps) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [agentId, setAgentId] = useState("");
  const [confirmingAgentId, setConfirmingAgentId] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignmentError, setAssignmentError] = useState("");
  const detail = usePolicy(apiKey, connectionId, policy.id, expanded);
  const rules = detail.data?.rules;
  const ruleRows = rules
    ? [
        { label: "Maximum per call", value: formatMoney(rules.maximum_per_call) },
        { label: "Daily budget", value: formatMoney(rules.daily_budget) },
        { label: "Monthly budget", value: formatMoney(rules.monthly_budget) },
        { label: "Approval threshold", value: formatMoney(rules.approval_threshold) },
        {
          label: "Allowed capabilities",
          value: formatRuleList(rules.allowed_capabilities, "All capabilities"),
        },
        {
          label: "Allowed providers",
          value: formatRuleList(rules.allowed_providers, "All providers"),
        },
        {
          label: "Blocked providers",
          value: formatRuleList(rules.blocked_providers, "None"),
        },
        {
          label: "Allowed contracts (not enforced)",
          value: formatRuleList(rules.allowed_contracts, "Any contract"),
        },
        {
          label: "Minimum provider reputation",
          value:
            rules.minimum_provider_reputation == null
              ? "Not set"
              : `${(rules.minimum_provider_reputation * 100).toFixed(1)}%`,
        },
        {
          label: "Minimum provider success",
          value:
            rules.minimum_provider_success_rate == null
              ? "Not set"
              : `${(rules.minimum_provider_success_rate * 100).toFixed(1)}%`,
        },
        {
          label: "Maximum accepted latency",
          value:
            rules.maximum_accepted_latency_ms == null
              ? "Not set"
              : `${rules.maximum_accepted_latency_ms} ms`,
        },
        {
          label: "Maximum consecutive failures",
          value:
            rules.maximum_consecutive_failures == null
              ? "Not set"
                          : `${rules.maximum_consecutive_failures}; gateway currently reports zero failures`,
        },
        {
          label: "Maximum drawdown (not enforced)",
          value: formatMoney(rules.maximum_drawdown),
        },
        {
          label: "Session expiry (not enforced)",
          value:
            rules.session_expiry_seconds == null
              ? "Not set"
              : `${rules.session_expiry_seconds} seconds`,
        },
        {
          label: "Allowed currencies",
          value: formatRuleList(rules.allowed_currencies, "Any currency"),
        },
      ]
    : [];

  async function submitAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedAgentId = agentId.trim();
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidPattern.test(normalizedAgentId)) {
      setAssignmentError("Enter a valid agent UUID from the Agents page.");
      return;
    }
    if (
      detail.data?.assignments.some(
        (item) => item.agent_id.toLowerCase() === normalizedAgentId.toLowerCase(),
      )
    ) {
      setAssignmentError("This policy is already assigned to that agent.");
      return;
    }
    setAssignmentError("");
    setConfirmingAgentId(normalizedAgentId);
  }

  async function confirmAssignment() {
    if (!confirmingAgentId) return;
    setAssigning(true);
    setAssignmentError("");
    try {
      await assignPolicy(apiKey, policy.id, confirmingAgentId);
      setAgentId("");
      setConfirmingAgentId("");
      await queryClient.invalidateQueries({
        queryKey: ["policy-detail", connectionId, policy.id],
      });
    } catch (error) {
      setAssignmentError(assignmentErrorMessage(error));
    } finally {
      setAssigning(false);
    }
  }

  return (
    <>
      <tr>
        <td>
          <div className="cell-stack">
            <strong>{policy.name}</strong>
            <span title={policy.description ?? undefined}>
              {policy.description || "No description provided"}
            </span>
          </div>
        </td>
        <td>
          <code className="primary-cell mono" title={policy.id}>
            {shortId(policy.id)}
          </code>
        </td>
        <td>
          <span className="status neutral">
            {policy.mode[0].toUpperCase() + policy.mode.slice(1)}
          </span>
        </td>
        <td className="primary-cell">v{policy.version}</td>
        <td>
          <span className={`status ${policy.is_active ? "active" : "neutral"}`}>
            {policy.is_active ? "Active" : "Inactive"}
          </span>
        </td>
        <td>
          <button
            className="button ghost"
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Hide rules" : "View rules"}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr className="policy-detail-table-row">
          <td colSpan={6}>
            {detail.isPending ? (
              <p role="status">Loading the complete policy and assignments…</p>
            ) : detail.isError ? (
              <div className="policy-detail-error" role="alert">
                <p>{detailErrorMessage(detail.error)}</p>
                <button
                  className="button ghost"
                  type="button"
                  onClick={() => void detail.refetch()}
                >
                  Try again
                </button>
              </div>
            ) : detail.data ? (
              <div className="policy-detail-content">
                <div className="policy-rule-section">
                  <div className="eyebrow">Stored rule configuration</div>
                  <p className="policy-rule-note">
                    The current evaluator does not enforce allowed contracts,
                    maximum drawdown, or session expiry. Failure thresholds have
                    no live history because the gateway currently reports zero
                    consecutive failures.
                  </p>
                  <dl className="policy-rule-grid">
                    {ruleRows.map((rule) => (
                      <div key={rule.label}>
                        <dt>{rule.label}</dt>
                        <dd>{rule.value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div className="policy-assignment-section">
                  <div>
                    <div className="eyebrow">Assigned agents</div>
                    {detail.data.assignments.length ? (
                      <ul className="policy-assignment-list">
                        {detail.data.assignments.map((assignment) => (
                          <li key={assignment.id}>
                            <code title={assignment.agent_id}>{shortId(assignment.agent_id)}</code>
                            <span>Assigned {formatAssignedDate(assignment.assigned_at)}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="card-description">This policy is not assigned to an agent.</p>
                    )}
                  </div>
                  <form className="policy-assign-form" onSubmit={submitAssignment}>
                    <label className="policy-form-field">
                      <span>Assign to agent UUID</span>
                      <input
                        className="search"
                        value={agentId}
                        disabled={Boolean(confirmingAgentId) || assigning}
                        onChange={(event) => setAgentId(event.target.value)}
                        placeholder="Copy the ID from Agents"
                        aria-label={`Agent UUID to assign ${policy.name}`}
                      />
                    </label>
                    <p className="policy-form-hint">
                      Copy the ID from the <a href="/agents" target="_blank" rel="noreferrer">Agents page (opens in a new tab)</a> so your workspace session stays connected. Assignment requires policies:write.
                    </p>
                    {assignmentError ? (
                      <p className="form-error" role="alert">
                        {assignmentError}
                      </p>
                    ) : null}
                    {confirmingAgentId ? (
                      <div
                        className="policy-assignment-confirm"
                        role="group"
                        aria-label="Confirm policy assignment"
                      >
                        <p>
                          Assign this policy to <code>{confirmingAgentId}</code>?
                          It can affect this agent&apos;s future requests.
                        </p>
                        <div className="page-actions">
                          <button
                            className="button primary"
                            type="button"
                            onClick={() => void confirmAssignment()}
                            disabled={assigning}
                          >
                            {assigning ? "Assigning…" : "Confirm assignment"}
                          </button>
                          <button
                            className="button ghost"
                            type="button"
                            onClick={() => setConfirmingAgentId("")}
                            disabled={assigning}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        className="button primary"
                        type="submit"
                        disabled={assigning || !agentId.trim()}
                      >
                        Review assignment
                      </button>
                    )}
                  </form>
                </div>
              </div>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}
