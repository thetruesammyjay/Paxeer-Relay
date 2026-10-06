"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import { useExecutionAttempts, useTransactions } from "@/hooks/use-transactions";
import type { Transaction } from "@/hooks/use-transactions";
import { ApiError } from "@/lib/api-client";

const REQUEST_STATES = [
  "created",
  "policy_pending",
  "approval_pending",
  "payment_required",
  "payment_submitted",
  "payment_verified",
  "execution_reserved",
  "executing",
  "delivered",
  "failed",
  "expired",
  "cancelled",
];

const PAYMENT_STATES = [
  "unpaid",
  "quoted",
  "submitted",
  "verified",
  "settled_layerx",
  "anchored_l1",
  "refunded",
  "disputed",
  "failed",
  "expired",
];

const STATE_LABELS: Record<string, string> = {
  approval_pending: "Approval pending",
  payment_required: "Payment required",
  payment_submitted: "Payment submitted",
  payment_verified: "Payment verified",
  execution_reserved: "Execution reserved",
  settled_layerx: "Settled on LayerX",
  anchored_l1: "Anchored on L1",
  not_started: "Not started",
  provider_error: "Provider error",
};

function stateLabel(value: string) {
  return (
    STATE_LABELS[value] ??
    value
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

function stateTone(value: string) {
  if (
    [
      "delivered",
      "succeeded",
      "verified",
      "payment_verified",
      "settled_layerx",
      "anchored_l1",
    ].includes(value)
  ) {
    return "verified";
  }
  if (
    [
      "failed",
      "expired",
      "cancelled",
      "disputed",
      "provider_error",
      "timeout",
      "unknown",
    ].includes(value)
  ) {
    return "denied";
  }
  if (["executing", "running", "execution_reserved", "reserved"].includes(value)) {
    return "routing";
  }
  if (
    [
      "approval_pending",
      "payment_required",
      "payment_submitted",
      "quoted",
      "submitted",
    ].includes(value)
  ) {
    return "pending";
  }
  return "neutral";
}

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function displayDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) {
      return "Your current project access needs transactions:read permission.";
    }
    if (error.status === 404) {
      return "The transaction history endpoint was not found. Update the API and try again.";
    }
    return `Transactions could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function includesSearch(transaction: Transaction, query: string) {
  return [
    transaction.id,
    transaction.agent_id,
    transaction.capability,
    transaction.request_state,
    transaction.payment_state,
    transaction.execution_state,
  ].some((value) => value.toLowerCase().includes(query));
}

export function TransactionActivity() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [requestState, setRequestState] = useState("");
  const [paymentState, setPaymentState] = useState("");
  const [search, setSearch] = useState("");
  const [expandedTransactionId, setExpandedTransactionId] = useState<string | null>(null);

  const query = useTransactions({
    apiKey,
    connectionId,
    requestState,
    paymentState,
  });
  const attemptsQuery = useExecutionAttempts({
    apiKey,
    connectionId,
    toolCallId: expandedTransactionId,
  });

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({
          queryKey: ["transactions", activeConnectionId],
        });
        queryClient.removeQueries({
          queryKey: ["execution-attempts", activeConnectionId],
        });
      }
    };
  }, [connectionId, queryClient]);

  function connect(key: string) {
    setApiKey(key);
    setConnectionId(globalThis.crypto.randomUUID());
    setExpandedTransactionId(null);
  }

  function disconnect() {
    if (connectionId) {
      queryClient.removeQueries({ queryKey: ["transactions", connectionId] });
      queryClient.removeQueries({ queryKey: ["execution-attempts", connectionId] });
    }
    setApiKey("");
    setConnectionId("");
    setRequestState("");
    setPaymentState("");
    setSearch("");
    setExpandedTransactionId(null);
  }

  const normalizedSearch = search.trim().toLowerCase();
  const hasFilters = Boolean(normalizedSearch || requestState || paymentState);
  const transactions = useMemo(
    () =>
      (query.data ?? []).filter((transaction) =>
        includesSearch(transaction, normalizedSearch),
      ),
    [query.data, normalizedSearch],
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Execution ledger</div>
          <h1 className="page-title">Transactions</h1>
          <p className="page-subtitle">
            Follow each request through its request, payment, and execution
            states.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh activity"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="transactions:read"
        actionLabel="Load transactions"
        apiKey={apiKey}
        connected={query.isSuccess && !query.isError}
        loading={query.isFetching}
        error={query.isError ? keyErrorMessage(query.error) : ""}
        onConnect={connect}
        onDisconnect={disconnect}
      />

      {!apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">
            TX
          </div>
          <div>
            <h2>Your request history will appear here</h2>
            <p>
              Connect to a workspace to see recent tool calls and their payment
              and execution states. No sample transactions are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading transaction history</h2>
            <p>Your project access is being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Transaction history is unavailable</h2>
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
              aria-label="Search recent transactions"
              placeholder="Search ID, agent, or capability"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Request</span>
              <select
                className="search transaction-filter"
                value={requestState}
                onChange={(event) => setRequestState(event.target.value)}
                aria-label="Filter by request state"
              >
                <option value="">All request states</option>
                {REQUEST_STATES.map((state) => (
                  <option key={state} value={state}>
                    {stateLabel(state)}
                  </option>
                ))}
              </select>
            </label>
            <label className="transaction-filter-label">
              <span>Payment</span>
              <select
                className="search transaction-filter"
                value={paymentState}
                onChange={(event) => setPaymentState(event.target.value)}
                aria-label="Filter by payment state"
              >
                <option value="">All payment states</option>
                {PAYMENT_STATES.map((state) => (
                  <option key={state} value={state}>
                    {stateLabel(state)}
                  </option>
                ))}
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {transactions.length} shown · up to 100 recent records
            </span>
          </div>

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">Recent requests</h2>
                <p className="card-description">
                  Refreshes every 30 seconds while this page is active. The API
                  returns identifiers, capabilities, lifecycle states, and
                  creation times.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {transactions.length === 0 ? (
              <div className="data-access-empty">
                <h3>
                  {hasFilters ? "No matching requests" : "No requests found"}
                </h3>
                <p>
                  {hasFilters
                    ? "Try another search or clear the state filters."
                    : "Requests will appear here after an agent calls a service."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table transaction-table">
                  <thead>
                    <tr>
                      <th scope="col">Request</th>
                      <th scope="col">Agent</th>
                      <th scope="col">Capability</th>
                      <th scope="col">Request state</th>
                      <th scope="col">Payment state</th>
                      <th scope="col">Execution state</th>
                      <th scope="col">Created</th>
                      <th scope="col">
                        <span className="settlement-visually-hidden">Details</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((transaction) => (
                      <Fragment key={transaction.id}>
                        <tr>
                          <td>
                            <code className="transaction-id" title={transaction.id}>
                              {shortId(transaction.id)}
                            </code>
                          </td>
                          <td>
                            <code className="transaction-id" title={transaction.agent_id}>
                              {shortId(transaction.agent_id)}
                            </code>
                          </td>
                          <td className="transaction-capability">
                            {transaction.capability}
                          </td>
                          <td>
                            <span className={`status ${stateTone(transaction.request_state)}`}>
                              {stateLabel(transaction.request_state)}
                            </span>
                          </td>
                          <td>
                            <span className={`status ${stateTone(transaction.payment_state)}`}>
                              {stateLabel(transaction.payment_state)}
                            </span>
                          </td>
                          <td>
                            <span className={`status ${stateTone(transaction.execution_state)}`}>
                              {stateLabel(transaction.execution_state)}
                            </span>
                          </td>
                          <td className="transaction-date">
                            {displayDate(transaction.created_at)}
                          </td>
                          <td>
                            <button
                              className="button transaction-details-button"
                              type="button"
                              aria-expanded={expandedTransactionId === transaction.id}
                              aria-controls={
                                expandedTransactionId === transaction.id
                                  ? `attempts-${transaction.id}`
                                  : undefined
                              }
                              onClick={() =>
                                setExpandedTransactionId((current) =>
                                  current === transaction.id ? null : transaction.id,
                                )
                              }
                            >
                              {expandedTransactionId === transaction.id
                                ? "Hide attempts"
                                : "Details"}
                            </button>
                          </td>
                        </tr>
                        {expandedTransactionId === transaction.id ? (
                          <tr>
                            <td id={`attempts-${transaction.id}`} colSpan={8}>
                              <div className="execution-attempt-panel">
                                {transaction.execution_state === "unknown" ? (
                                  <div className="execution-unknown-warning" role="note">
                                    <strong>Outcome unknown.</strong> The provider may have completed this action.
                                    Check the provider before retrying; PaxRelay will not replay it automatically.
                                  </div>
                                ) : null}
                                <div className="execution-attempt-heading">
                                  <h3>Provider attempts</h3>
                                  <span className="card-meta">Operational metadata only</span>
                                </div>
                                {attemptsQuery.isPending ? (
                                  <p role="status">Loading attempt detailsâ€¦</p>
                                ) : attemptsQuery.isError ? (
                                  <div role="alert" className="data-access-error">
                                    Attempt details could not be loaded. Check your
                                    transactions:read access and try again.
                                  </div>
                                ) : attemptsQuery.data?.length ? (
                                  <div className="table-wrap">
                                    <table className="data-table execution-attempt-table">
                                      <thead>
                                        <tr>
                                          <th scope="col">Attempt</th>
                                          <th scope="col">Provider</th>
                                          <th scope="col">State</th>
                                          <th scope="col">Forwarded</th>
                                          <th scope="col">Response</th>
                                          <th scope="col">Latency</th>
                                          <th scope="col">HTTP</th>
                                          <th scope="col">Provider error</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {attemptsQuery.data.map((attempt) => (
                                          <tr key={attempt.id}>
                                            <td>{attempt.attempt_number}</td>
                                            <td>
                                              <code
                                                className="transaction-id"
                                                title={attempt.provider_id}
                                              >
                                                {shortId(attempt.provider_id)}
                                              </code>
                                            </td>
                                            <td>
                                              <span
                                                className={`status ${stateTone(attempt.execution_state)}`}
                                              >
                                                {stateLabel(attempt.execution_state)}
                                              </span>
                                            </td>
                                            <td>
                                              {attempt.request_forwarded_at
                                                ? displayDate(attempt.request_forwarded_at)
                                                : "â€”"}
                                            </td>
                                            <td>
                                              {attempt.response_received_at
                                                ? displayDate(attempt.response_received_at)
                                                : "â€”"}
                                            </td>
                                            <td>
                                              {attempt.latency_ms === null
                                                ? "â€”"
                                                : `${attempt.latency_ms} ms`}
                                            </td>
                                            <td>{attempt.http_status_code ?? "â€”"}</td>
                                            <td>{attempt.provider_error_code ?? "â€”"}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                ) : (
                                  <p>No provider attempts are recorded for this request.</p>
                                )}
                                <p className="execution-attempt-footnote">
                                  Request contents, provider responses, and payment credentials are not included here.
                                </p>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
