"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import { useReceipts } from "@/hooks/use-receipts";
import type { ReceiptRecord } from "@/hooks/use-receipts";
import { ApiError } from "@/lib/api-client";

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

function statusTone(status: string) {
  if (status === "succeeded") return "active";
  if (["failed", "provider_error", "timeout", "cancelled", "unknown"].includes(status)) {
    return "denied";
  }
  if (["running", "reserved"].includes(status)) return "routing";
  return "neutral";
}

function statusLabel(status: string) {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) {
      return "Your current project access needs receipts:read permission.";
    }
    if (error.status === 404) {
      return "The receipts endpoint was not found. Update the API and try again.";
    }
    return `Receipt records could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function matchesSearch(receipt: ReceiptRecord, search: string) {
  return [
    receipt.id,
    receipt.tool_call_id,
    receipt.agent_id,
    receipt.provider_id,
    receipt.service_id,
    receipt.service_version,
    receipt.capability,
    receipt.payment_amount,
    receipt.payment_currency,
    receipt.payment_scheme,
    receipt.payment_network ?? "",
    receipt.payment_asset ?? "",
    receipt.payment_transaction ?? "",
    receipt.layerx_transaction ?? "",
    receipt.execution_status,
    receipt.request_hash,
    receipt.response_hash,
    receipt.receipt_hash ?? "",
    receipt.signature ?? "",
    receipt.signing_key_id ?? "",
  ].some((value) => value.toLowerCase().includes(search));
}

function ReceiptEvidence({ receipt }: { receipt: ReceiptRecord }) {
  return (
    <details className="receipt-evidence">
      <summary>Receipt evidence</summary>
      <dl>
        <div>
          <dt>Receipt hash</dt>
          <dd>{receipt.receipt_hash ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Payment rail</dt>
          <dd>{receipt.payment_scheme} · {receipt.payment_network ?? "Network not recorded"}</dd>
        </div>
        <div>
          <dt>Payment asset</dt>
          <dd>{receipt.payment_asset ?? receipt.payment_currency}</dd>
        </div>
        <div>
          <dt>Payment transaction</dt>
          <dd>{receipt.payment_transaction ?? receipt.layerx_transaction ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Signing key</dt>
          <dd>{receipt.signing_key_id ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Signature</dt>
          <dd>{receipt.signature ?? "Not recorded"}</dd>
        </div>
        <div>
          <dt>Request hash</dt>
          <dd>{receipt.request_hash}</dd>
        </div>
        <div>
          <dt>Response hash</dt>
          <dd>{receipt.response_hash}</dd>
        </div>
        <div>
          <dt>Tool call</dt>
          <dd>{receipt.tool_call_id}</dd>
        </div>
        <div>
          <dt>Provider / service</dt>
          <dd>
            {receipt.provider_id} / {receipt.service_id} v{receipt.service_version}
          </dd>
        </div>
      </dl>
      <p>Evidence is displayed as returned by the API; this page does not verify the signature.</p>
    </details>
  );
}

export function ReceiptDirectory() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [search, setSearch] = useState("");
  const [executionStatus, setExecutionStatus] = useState("");
  const query = useReceipts(apiKey, connectionId);

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({ queryKey: ["receipts", activeConnectionId] });
      }
    };
  }, [connectionId, queryClient]);

  function connect(key: string) {
    setApiKey(key);
    setConnectionId(globalThis.crypto.randomUUID());
  }

  function disconnect() {
    if (connectionId) {
      queryClient.removeQueries({ queryKey: ["receipts", connectionId] });
    }
    setApiKey("");
    setConnectionId("");
    setSearch("");
    setExecutionStatus("");
  }

  const normalizedSearch = search.trim().toLowerCase();
  const statuses = useMemo(
    () => [...new Set((query.data ?? []).map((receipt) => receipt.execution_status))].sort(),
    [query.data],
  );
  const receipts = useMemo(
    () =>
      (query.data ?? []).filter(
        (receipt) =>
          (!executionStatus || receipt.execution_status === executionStatus) &&
          matchesSearch(receipt, normalizedSearch),
      ),
    [query.data, executionStatus, normalizedSearch],
  );
  const hasFilters = Boolean(normalizedSearch || executionStatus);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Service execution evidence</div>
          <h1 className="page-title">Receipts</h1>
          <p className="page-subtitle">
            Review receipt summaries and available signature metadata for service calls.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh receipts"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="receipts:read"
        actionLabel="Load receipts"
        apiKey={apiKey}
        connected={query.isSuccess && !query.isError}
        loading={query.isFetching}
        error={query.isError ? keyErrorMessage(query.error) : ""}
        onConnect={connect}
        onDisconnect={disconnect}
      />

      {!apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">RC</div>
          <div>
            <h2>Your receipt records will appear here</h2>
            <p>
              Connect to a workspace to see the latest receipt summaries for
              the selected project and environment. No sample receipts are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">…</div>
          <div>
            <h2>Loading receipt records</h2>
            <p>Your project access is being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Receipt records are unavailable</h2>
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
              aria-label="Search receipt records"
              placeholder="Search receipt, agent, capability, or payment reference"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Execution</span>
              <select
                className="search transaction-filter"
                value={executionStatus}
                onChange={(event) => setExecutionStatus(event.target.value)}
                aria-label="Filter by execution status"
              >
                <option value="">All execution states</option>
                {statuses.map((status) => (
                  <option key={status} value={status}>{statusLabel(status)}</option>
                ))}
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {receipts.length} shown · up to 100 recent records
            </span>
          </div>

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">Recent receipt summaries</h2>
                <p className="card-description">
                  Refreshes every 30 seconds. Payment amounts are shown in exact
                  atomic units. Evidence fields are not cryptographically verified here.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {receipts.length === 0 ? (
              <div className="data-access-empty">
                <h3>{hasFilters ? "No matching receipts" : "No receipts found"}</h3>
                <p>
                  {hasFilters
                    ? "Try another search or clear the execution filter."
                    : "Receipt summaries will appear after service calls produce records."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table receipt-directory-table">
                  <thead>
                    <tr>
                      <th scope="col">Receipt</th>
                      <th scope="col">Agent</th>
                      <th scope="col">Capability</th>
                      <th scope="col">Payment (atomic units)</th>
                      <th scope="col">Execution</th>
                      <th scope="col">Latency</th>
                      <th scope="col">Issued</th>
                      <th scope="col">Settlement transaction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {receipts.map((receipt) => (
                      <tr key={receipt.id}>
                        <td>
                          <div className="cell-stack">
                            <code className="mono" title={receipt.id}>{shortId(receipt.id)}</code>
                            <ReceiptEvidence receipt={receipt} />
                          </div>
                        </td>
                        <td><code className="mono" title={receipt.agent_id}>{shortId(receipt.agent_id)}</code></td>
                        <td><code className="service-capability">{receipt.capability}</code></td>
                        <td className="amount" title="Exact integer amount in atomic units">
                          {receipt.payment_amount} {receipt.payment_currency}
                        </td>
                        <td>
                          <span className={`status ${statusTone(receipt.execution_status)}`}>
                            {statusLabel(receipt.execution_status)}
                          </span>
                        </td>
                        <td>{receipt.execution_latency_ms.toLocaleString()} ms</td>
                        <td>{displayDate(receipt.issued_at)}</td>
                        <td>
                          {(receipt.payment_transaction ?? receipt.layerx_transaction) ? (
                            <code
                              className="mono"
                              title={receipt.payment_transaction ?? receipt.layerx_transaction ?? ""}
                            >
                              {shortId(receipt.payment_transaction ?? receipt.layerx_transaction ?? "")}
                            </code>
                          ) : <span className="muted">Not recorded</span>}
                        </td>
                      </tr>
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
