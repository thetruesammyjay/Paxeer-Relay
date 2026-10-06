"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { HugeiconsIcon } from "@hugeicons/react";
import { ShieldCheckIcon } from "@hugeicons/core-free-icons";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import {
  useApprovals,
  useDecideApproval,
  type Approval,
  type ApprovalDecision,
} from "@/hooks/use-approvals";
import { ApiError } from "@/lib/api-client";

const APPROVAL_STATUSES = [
  "pending",
  "approved",
  "rejected",
  "expired",
  "consumed",
  "invalidated",
] as const;

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function displayDate(value: string | null) {
  if (!value) return "No expiry set";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function displayAmount(approval: Approval) {
  if (!/^\d+$/.test(approval.amount_atomic)) {
    return `${approval.amount_atomic} atomic ${approval.currency}`;
  }
  if (!Number.isInteger(approval.decimals) || approval.decimals < 0 || approval.decimals > 30) {
    return `${approval.amount_atomic} atomic ${approval.currency}`;
  }

  const amount = BigInt(approval.amount_atomic);
  const scale = 10n ** BigInt(approval.decimals);
  const whole = amount / scale;
  if (approval.decimals === 0) return `${whole.toLocaleString()} ${approval.currency}`;

  const fraction = (amount % scale)
    .toString()
    .padStart(approval.decimals, "0")
    .replace(/0+$/, "");
  return `${whole.toLocaleString()}${fraction ? `.${fraction}` : ""} ${approval.currency}`;
}

function stateLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function stateTone(value: string) {
  if (value === "pending") return "pending";
  if (value === "approved") return "active";
  if (value === "rejected") return "denied";
  if (value === "consumed") return "verified";
  return "neutral";
}

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) {
      return "Your current project access needs approvals:read and approvals:write permissions.";
    }
    if (error.status === 404) {
      return "The approvals endpoint was not found. Update the API and try again.";
    }
    return `Approvals could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function decisionErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) return "Your current project access needs approvals:write permission to record decisions.";
    if (error.status === 409) {
      return "This request already has a decision or is no longer actionable. Refresh the queue.";
    }
    if (error.status === 404) return "This approval request is no longer available.";
    return `The decision could not be saved (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. The decision was not confirmed.";
}

function matchesSearch(approval: Approval, query: string) {
  return [
    approval.id,
    approval.tool_call_id,
    approval.agent_id,
    approval.capability,
    approval.provider_id ?? "",
    approval.policy_id ?? "",
    approval.request_hash ?? "",
    approval.reason ?? "",
    approval.status,
    displayAmount(approval),
  ].some((value) => value.toLowerCase().includes(query));
}

export function ApprovalQueue() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [keyValidated, setKeyValidated] = useState(false);
  const [connectionId, setConnectionId] = useState("");
  const [status, setStatus] = useState("pending");
  const [search, setSearch] = useState("");
  const [selectedDecision, setSelectedDecision] = useState<{
    approvalId: string;
    decision: ApprovalDecision;
  } | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionError, setDecisionError] = useState("");
  const [notice, setNotice] = useState("");
  const query = useApprovals(apiKey, connectionId, status);
  const decisionMutation = useDecideApproval(apiKey, connectionId);

  useEffect(() => {
    if (query.isSuccess) setKeyValidated(true);
    if (query.isError) setKeyValidated(false);
  }, [query.isError, query.isSuccess]);

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({
          queryKey: ["approvals", activeConnectionId],
        });
      }
    };
  }, [connectionId, queryClient]);

  function connect(key: string) {
    setApiKey(key);
    setKeyValidated(false);
    setConnectionId(globalThis.crypto.randomUUID());
    setNotice("");
  }

  function disconnect() {
    if (connectionId) {
      queryClient.removeQueries({ queryKey: ["approvals", connectionId] });
    }
    setApiKey("");
    setKeyValidated(false);
    setConnectionId("");
    setStatus("pending");
    setSearch("");
    setSelectedDecision(null);
    setDecisionReason("");
    setDecisionError("");
    setNotice("");
  }

  function startDecision(approvalId: string, decision: ApprovalDecision) {
    setSelectedDecision({ approvalId, decision });
    setDecisionReason("");
    setDecisionError("");
    setNotice("");
  }

  function cancelDecision() {
    setSelectedDecision(null);
    setDecisionReason("");
    setDecisionError("");
  }

  async function submitDecision() {
    if (!selectedDecision) return;
    setDecisionError("");
    try {
      const result = await decisionMutation.mutateAsync({
        ...selectedDecision,
        reason: decisionReason.trim() || undefined,
      });
      setNotice(
        result.status === "expired"
          ? "This request expired before the decision could be recorded. The queue is up to date."
          : `Decision recorded: ${stateLabel(result.status)}.`,
      );
      setSelectedDecision(null);
      setDecisionReason("");
    } catch (error) {
      setDecisionError(decisionErrorMessage(error));
    }
  }

  const normalizedSearch = search.trim().toLowerCase();
  const approvals = useMemo(
    () =>
      (query.data ?? []).filter((approval) =>
        matchesSearch(approval, normalizedSearch),
      ),
    [query.data, normalizedSearch],
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Human authority</div>
          <h1 className="page-title">Approvals</h1>
          <p className="page-subtitle">
            Review policy-gated requests before they continue to payment.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching || decisionMutation.isPending}
          >
            {query.isFetching ? "Refreshing…" : "Refresh queue"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="approvals:read"
        additionalScopes={["approvals:write"]}
        actionLabel="Load approval queue"
        apiKey={apiKey}
        connected={keyValidated && !query.isError}
        loading={query.isFetching || decisionMutation.isPending}
        error={query.isError ? keyErrorMessage(query.error) : ""}
        onConnect={connect}
        onDisconnect={disconnect}
      />

      {!apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">
            AP
          </div>
          <div>
            <h2>The approval queue will appear here</h2>
            <p>
              Connect to a workspace with read and decision access to review requests.
              No sample approvals are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading approval queue</h2>
            <p>Your project access is being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Approval queue is unavailable</h2>
            <p>{keyErrorMessage(query.error)}</p>
          </div>
          <button
            className="button"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            Try again
          </button>
        </section>
      ) : (
        <>
          <div className="transaction-toolbar toolbar">
            <input
              className="search"
              type="search"
              aria-label="Search approval requests"
              placeholder="Search agent, capability, ID, or reason"
              value={search}
              disabled={decisionMutation.isPending}
              onChange={(event) => {
                cancelDecision();
                setSearch(event.target.value);
              }}
            />
            <label className="transaction-filter-label">
              <span>Request status</span>
              <select
                className="search transaction-filter"
                value={status}
                disabled={decisionMutation.isPending}
                onChange={(event) => {
                  cancelDecision();
                  setStatus(event.target.value);
                }}
                aria-label="Filter approvals by request status"
              >
                <option value="">All statuses</option>
                {APPROVAL_STATUSES.map((approvalStatus) => (
                  <option key={approvalStatus} value={approvalStatus}>
                    {stateLabel(approvalStatus)}
                  </option>
                ))}
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {approvals.length} shown · up to 100 recent requests
            </span>
          </div>

          {notice ? (
            <div className="data-access-notice" role="status">
              {notice}
            </div>
          ) : null}

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">
                  {status ? `${stateLabel(status)} requests` : "All approval requests"}
                </h2>
                <p className="card-description">
                  Refreshes every 30 seconds. Approval permits the request to
                  continue; it does not verify or submit a payment.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {approvals.length === 0 ? (
              <div className="data-access-empty">
                <h3>{normalizedSearch ? "No matching requests" : "No requests found"}</h3>
                <p>
                  {normalizedSearch
                    ? "Try another search or clear the search field."
                    : status === "pending"
                      ? "There are no pending requests for this project and environment."
                      : "Approval requests will appear here when a policy requires a decision."}
                </p>
              </div>
            ) : (
              <div className="approval-queue">
                {approvals.map((approval) => {
                  const isSelected = selectedDecision?.approvalId === approval.id;
                  const isPending = approval.status === "pending";

                  return (
                    <article className="approval approval-card" key={approval.id}>
                      <div className="approval-top">
                        <span className="approval-mark" aria-hidden="true">
                          <HugeiconsIcon
                            icon={ShieldCheckIcon}
                            size={18}
                            color="currentColor"
                            strokeWidth={1.8}
                          />
                        </span>
                        <div className="approval-heading">
                          <div className="approval-title-row">
                            <h3>{approval.capability}</h3>
                            <span className={`status ${stateTone(approval.status)}`}>
                              {stateLabel(approval.status)}
                            </span>
                          </div>
                          <p>
                            {approval.reason || "This request was sent for human review by policy."}
                          </p>
                          <span className="approval-id" title={approval.id}>
                            Request {shortId(approval.id)} · Agent {shortId(approval.agent_id)}
                          </span>
                        </div>
                      </div>

                      <div className="approval-facts">
                        <div className="approval-fact">
                          <span>Requested amount</span>
                          <strong>{displayAmount(approval)}</strong>
                        </div>
                        <div className="approval-fact">
                          <span>Created</span>
                          <strong>{displayDate(approval.created_at)}</strong>
                        </div>
                        <div className="approval-fact">
                          <span>Expires</span>
                          <strong>{displayDate(approval.expires_at)}</strong>
                        </div>
                      </div>

                      <div className="approval-reference-row">
                        <span>
                          Policy: {approval.policy_id ? shortId(approval.policy_id) : "Not recorded"}
                          {approval.policy_version ? ` · v${approval.policy_version}` : ""}
                        </span>
                        <span title={approval.tool_call_id}>
                          Tool call: {shortId(approval.tool_call_id)}
                        </span>
                        {approval.recipient_address ? (
                          <code title={approval.recipient_address}>
                            Recipient {shortId(approval.recipient_address)}
                          </code>
                        ) : null}
                        {approval.provider_id ? (
                          <span title={approval.provider_id}>
                            Provider {shortId(approval.provider_id)}
                          </span>
                        ) : null}
                        {approval.service_version_id ? (
                          <span title={approval.service_version_id}>
                            Service version {shortId(approval.service_version_id)}
                          </span>
                        ) : null}
                      </div>

                      {isSelected && selectedDecision ? (
                        <div className="approval-confirmation">
                          <h4>
                            Confirm {selectedDecision.decision === "approved" ? "approval" : "rejection"}
                          </h4>
                          <p>
                            {selectedDecision.decision === "approved"
                              ? "This lets the request continue to payment checks."
                              : "This rejects the request and marks the tool call as failed."}
                          </p>
                          <label className="approval-reason-field">
                            <span>Decision note (optional)</span>
                            <textarea
                              maxLength={512}
                              rows={2}
                              value={decisionReason}
                              onChange={(event) => setDecisionReason(event.target.value)}
                              placeholder="Add context for the audit record"
                            />
                          </label>
                          {decisionError ? (
                            <p className="approval-decision-error" role="alert">
                              {decisionError}
                            </p>
                          ) : null}
                          <div className="approval-actions">
                            <button
                              className="button"
                              type="button"
                              onClick={cancelDecision}
                              disabled={decisionMutation.isPending}
                            >
                              Cancel
                            </button>
                            <button
                              className={`button ${selectedDecision.decision === "approved" ? "primary" : "danger"}`}
                              type="button"
                              onClick={() => void submitDecision()}
                              disabled={decisionMutation.isPending}
                            >
                              {decisionMutation.isPending
                                ? "Saving decision…"
                                : `Confirm ${selectedDecision.decision === "approved" ? "approval" : "rejection"}`}
                            </button>
                          </div>
                        </div>
                      ) : isPending ? (
                        <div className="approval-actions">
                          <button
                            className="button primary"
                            type="button"
                            onClick={() => startDecision(approval.id, "approved")}
                            disabled={decisionMutation.isPending}
                          >
                            Approve request
                          </button>
                          <button
                            className="button"
                            type="button"
                            onClick={() => startDecision(approval.id, "rejected")}
                            disabled={decisionMutation.isPending}
                          >
                            Reject request
                          </button>
                        </div>
                      ) : approval.decision_reason ? (
                        <p className="approval-decision-note">
                          Decision note: {approval.decision_reason}
                        </p>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
