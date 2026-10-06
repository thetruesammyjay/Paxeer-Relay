"use client";

import { useEffect, useState, type FormEvent } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { Invoice01Icon, ShieldCheckIcon } from "@hugeicons/core-free-icons";
import { useSettlementReconciliation } from "@/hooks/use-settlement-reconciliation";
import type {
  ReconciliationCursor,
  ReconciliationStatus,
  SettlementReconciliation,
} from "@/hooks/use-settlement-reconciliation";
import { ApiError } from "@/lib/api-client";
import { useApiSession } from "@/lib/api-session";
import { StatusBadge } from "@/components/status-badge";

const FILTERS: { value: ReconciliationStatus; label: string }[] = [
  { value: "mismatch", label: "Needs review" },
  { value: "awaiting_external", label: "Waiting for evidence" },
  { value: "layerx_confirmed", label: "LayerX confirmed" },
  { value: "reconciled", label: "Reconciled" },
];

const STATUS_LABELS: Record<string, string> = {
  mismatch: "Needs review",
  awaiting_external: "Waiting for evidence",
  layerx_confirmed: "LayerX confirmed",
  reconciled: "Reconciled",
  anchored: "Reconciled",
};

function labelForStatus(status: string): string {
  return STATUS_LABELS[status] ?? status.replaceAll("_", " ");
}

function displayFact(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value) ?? "Not available";
  } catch {
    return "Not available";
  }
}

function displayTime(value: string | null): string {
  if (!value) return "Not checked yet";
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "The API key was not accepted. Check the key and try again.";
    }
    if (error.status === 403) {
      return "This key needs settlements:read access for the same project and environment.";
    }
    if (error.status === 404) {
      return "The settlements endpoint was not found. Check that the API is running the current version.";
    }
    return `The API returned an error (${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check the API address and try again.";
}

function ReviewFacts({ record }: { record: SettlementReconciliation }) {
  const references = [
    ["LayerX transaction", record.layerx_transaction_hash],
    ["LayerX batch", record.layerx_batch_id],
    ["Settlement reference", record.l1_settlement_id],
    ["L1 block", record.l1_block_number],
    ["L1 transaction", record.l1_transaction_hash],
    ["Commitment", record.l1_commitment_hash],
  ] as const;
  const issues = record.mismatch_details?.issues ?? [];

  return (
    <section className="settlement-detail" aria-labelledby="settlement-detail-title">
      <header className="settlement-detail-head">
        <div>
          <p className="settlement-section-label">Selected payment</p>
          <h3 id="settlement-detail-title">Evidence and check history</h3>
        </div>
        <StatusBadge
          status={record.reconciliation_status}
          label={labelForStatus(record.reconciliation_status)}
        />
      </header>

      {issues.length > 0 ? (
        <div className="settlement-issues">
          {issues.map((issue, index) => (
            <article className="settlement-issue" key={`${issue.code}-${index}`}>
              <h4>{issue.code.replaceAll("_", " ")}</h4>
              {issue.expected !== undefined || issue.actual !== undefined ? (
                <div className="settlement-comparison">
                  <div>
                    <span>Expected</span>
                    <code>{displayFact(issue.expected)}</code>
                  </div>
                  <div>
                    <span>Recorded</span>
                    <code>{displayFact(issue.actual)}</code>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <p className="settlement-no-issues">
          No mismatch details are attached to this record.
        </p>
      )}

      <dl className="settlement-reference-grid">
        {references.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd title={value === null ? undefined : String(value)}>
              {displayFact(value)}
            </dd>
          </div>
        ))}
      </dl>

      <dl className="settlement-history-grid">
        <div>
          <dt>Payment state</dt>
          <dd>{labelForStatus(record.payment_state)}</dd>
        </div>
        <div>
          <dt>Last checked</dt>
          <dd>{displayTime(record.last_checked_at)}</dd>
        </div>
        <div>
          <dt>Next attempt</dt>
          <dd>{displayTime(record.next_attempt_at)}</dd>
        </div>
        <div>
          <dt>Attempts</dt>
          <dd>{record.attempt_count}</dd>
        </div>
        {record.last_error ? (
          <div>
            <dt>Last error</dt>
            <dd>{record.last_error.replaceAll("_", " ")}</dd>
          </div>
        ) : null}
      </dl>
    </section>
  );
}

export function SettlementReview() {
  const apiSession = useApiSession();
  const [draftToken, setDraftToken] = useState("");
  const [token, setToken] = useState("");
  const [connectionVersion, setConnectionVersion] = useState(0);
  const [keyFormOpen, setKeyFormOpen] = useState(true);
  const [status, setStatus] = useState<ReconciliationStatus>("mismatch");
  const [cursors, setCursors] = useState<(ReconciliationCursor | null)[]>([null]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pageIndex = cursors.length - 1;
  const cursor = cursors[pageIndex] ?? null;
  const query = useSettlementReconciliation({
    token: token || undefined,
    connectionVersion,
    status,
    cursor,
  });

  useEffect(() => {
    if (apiSession.apiKey && apiSession.apiKey !== token) {
      setToken(apiSession.apiKey);
      setConnectionVersion((version) => version + 1);
      setKeyFormOpen(false);
      setCursors([null]);
      setSelectedId(null);
    } else if (!apiSession.apiKey && token) {
      setToken("");
      setConnectionVersion((version) => version + 1);
      setKeyFormOpen(true);
      setCursors([null]);
      setSelectedId(null);
    }
  }, [apiSession.apiKey, token]);

  useEffect(() => {
    if (token && query.isSuccess) {
      setKeyFormOpen(false);
      setDraftToken("");
    }
  }, [token, query.isSuccess]);

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextToken = draftToken.trim();
    if (!nextToken) return;
    if (!(await apiSession.connect(nextToken))) return;
    setToken(nextToken);
    setConnectionVersion((version) => version + 1);
    setCursors([null]);
    setSelectedId(null);
  }

  function disconnect() {
    apiSession.disconnect();
    setToken("");
    setDraftToken("");
    setKeyFormOpen(true);
    setConnectionVersion((version) => version + 1);
    setCursors([null]);
    setSelectedId(null);
  }

  function changeStatus(nextStatus: ReconciliationStatus) {
    setStatus(nextStatus);
    setCursors([null]);
    setSelectedId(null);
  }

  const items = query.data?.items ?? [];
  const selectedRecord = items.find((item) => item.id === selectedId) ?? null;
  const nextCreatedAt = query.data?.next_cursor_created_at;
  const nextId = query.data?.next_cursor_id;
  const hasNext = Boolean(nextCreatedAt && nextId);

  function nextPage() {
    if (!nextCreatedAt || !nextId) return;
    setCursors((current) => [
      ...current.slice(0, pageIndex + 1),
      { createdAt: nextCreatedAt, id: nextId },
    ]);
    setSelectedId(null);
  }

  function previousPage() {
    if (pageIndex === 0) return;
    setCursors((current) => current.slice(0, -1));
    setSelectedId(null);
  }

  return (
    <div className="page settlement-page">
      <header className="settlement-page-head">
        <div>
          <div className="settlement-title-line">
            <HugeiconsIcon
              icon={Invoice01Icon}
              size={25}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
            <h1 className="page-title">Settlement review</h1>
          </div>
          <p className="page-subtitle">
            Compare payment records with settlement evidence and inspect issues
            that need a closer look.
          </p>
        </div>
        <div className="settlement-readonly-mark">
          <HugeiconsIcon
            icon={ShieldCheckIcon}
            size={17}
            color="currentColor"
            strokeWidth={1.7}
            aria-hidden="true"
          />
          Read-only
        </div>
      </header>

      <section className="settlement-access" aria-labelledby="settlement-access-title">
        <div className="settlement-access-copy">
          <span className="settlement-access-mark" aria-hidden="true">
            <HugeiconsIcon
              icon={ShieldCheckIcon}
              size={19}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
          </span>
          <div>
            <h2 id="settlement-access-title">Connect a read-only API key</h2>
            <p>
              Use a production key with <code>settlements:read</code> access.
              The API verifies the project and production environment before
              reconciliation data is loaded.
            </p>
          </div>
        </div>

        {keyFormOpen || !token ? (
          <form className="settlement-key-form" onSubmit={(event) => void connect(event)}>
            <label className="settlement-key-field">
              <span>API key</span>
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={draftToken}
                onChange={(event) => setDraftToken(event.target.value)}
                placeholder="Paste a production API key"
                aria-describedby="settlement-key-note"
                required
              />
            </label>
            <button
              className="button primary"
              type="submit"
              disabled={!draftToken.trim()}
            >
              Connect key
            </button>
            {token ? (
              <button
                className="button ghost settlement-key-cancel"
                type="button"
                onClick={() => {
                  setDraftToken("");
                  setKeyFormOpen(false);
                }}
              >
                Cancel
              </button>
            ) : null}
            <p id="settlement-key-note" className="settlement-key-note">
              Only production keys are accepted. The key stays in memory across
              dashboard pages and is cleared when you disconnect or reload.
            </p>
            {apiSession.error ? (
              <p className="api-session-error" role="alert">{apiSession.error}</p>
            ) : null}
          </form>
        ) : (
          <div className="settlement-connected">
            <span className={`settlement-connection-state ${query.isError ? "error" : "connected"}`}>
              <i aria-hidden="true" />
              {query.isError ? "Connection needs attention" : "Key connected for this tab"}
            </span>
            <button
              className="button ghost"
              type="button"
              onClick={() => setKeyFormOpen(true)}
            >
              Change key
            </button>
            <button className="button ghost" type="button" onClick={disconnect}>
              Disconnect
            </button>
          </div>
        )}
      </section>

      {query.isError ? (
        <div className="settlement-error" role="alert">
          <strong>Could not load reconciliation records.</strong>
          <span>{errorMessage(query.error)}</span>
        </div>
      ) : null}

      <section className="settlement-queue" aria-labelledby="settlement-queue-title">
        <header className="settlement-queue-head">
          <div>
            <h2 id="settlement-queue-title">Reconciliation queue</h2>
            <p>Records refresh automatically every 30 seconds.</p>
          </div>
          {token ? (
            <button
              className="button"
              type="button"
              onClick={() => void query.refetch()}
              disabled={query.isFetching}
            >
              {query.isFetching ? "Refreshing…" : "Refresh list"}
            </button>
          ) : null}
        </header>

        <div className="settlement-filter-row">
          <div className="settlement-filters" role="group" aria-label="Filter reconciliation records">
            {FILTERS.map((filter) => (
              <button
                key={filter.value}
                className={`settlement-filter ${status === filter.value ? "active" : ""}`}
                type="button"
                aria-pressed={status === filter.value}
                onClick={() => changeStatus(filter.value)}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <span className="settlement-result-count" aria-live="polite">
            {query.isSuccess
              ? `${items.length} ${items.length === 1 ? "record" : "records"} on this page`
              : token
                ? "Waiting for records"
                : "Connect a key to view records"}
          </span>
        </div>

        {!token ? (
          <div className="settlement-empty">
            <span className="settlement-empty-icon" aria-hidden="true">
              <HugeiconsIcon
                icon={Invoice01Icon}
                size={23}
                color="currentColor"
                strokeWidth={1.7}
              />
            </span>
            <h3>Connect a key to open the queue</h3>
            <p>Records are scoped to the project and environment on your API key.</p>
          </div>
        ) : query.isPending ? (
          <div className="settlement-empty" role="status">
            <span className="settlement-loading-mark" aria-hidden="true" />
            <h3>Loading reconciliation records</h3>
            <p>The API key and project access are being checked.</p>
          </div>
        ) : query.isError ? (
          <div className="settlement-empty settlement-empty-error">
            <h3>Records are unavailable</h3>
            <p>Update the API key or retry the request when the API is reachable.</p>
          </div>
        ) : items.length === 0 ? (
          <div className="settlement-empty">
            <span className="settlement-empty-icon" aria-hidden="true">
              <HugeiconsIcon
                icon={ShieldCheckIcon}
                size={23}
                color="currentColor"
                strokeWidth={1.7}
              />
            </span>
            <h3>
              {status === "mismatch"
                ? "Nothing needs review"
                : `No ${labelForStatus(status).toLowerCase()} records`}
            </h3>
            <p>
              {status === "mismatch"
                ? "No mismatches were returned for this project and environment."
                : "Try another status to see more reconciliation records."}
            </p>
          </div>
        ) : (
          <>
            <div className="table-wrap settlement-table-wrap">
              <table className="data-table settlement-table">
                <thead>
                  <tr>
                    <th scope="col">Payment</th>
                    <th scope="col">Payment state</th>
                    <th scope="col">Review status</th>
                    <th scope="col">LayerX reference</th>
                    <th scope="col">Last checked</th>
                    <th scope="col">
                      <span className="settlement-visually-hidden">Details</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((record) => (
                    <tr key={record.id}>
                      <td>
                        <code className="settlement-id" title={record.payment_id}>
                          {shortId(record.payment_id)}
                        </code>
                      </td>
                      <td>{labelForStatus(record.payment_state)}</td>
                      <td>
                        <StatusBadge
                          status={record.reconciliation_status}
                          label={labelForStatus(record.reconciliation_status)}
                        />
                      </td>
                      <td>
                        {record.layerx_transaction_hash ? (
                          <code className="settlement-reference" title={record.layerx_transaction_hash}>
                            {shortId(record.layerx_transaction_hash)}
                          </code>
                        ) : (
                          <span className="muted">Not available</span>
                        )}
                      </td>
                      <td>{displayTime(record.last_checked_at)}</td>
                      <td>
                        <button
                          className="settlement-open-button"
                          type="button"
                          aria-label={`Review payment ${shortId(record.payment_id)}`}
                          aria-expanded={selectedId === record.id}
                          onClick={() => setSelectedId(selectedId === record.id ? null : record.id)}
                        >
                          {selectedId === record.id ? "Close" : "Review"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="settlement-mobile-list">
              {items.map((record) => (
                <article className="settlement-mobile-record" key={record.id}>
                  <button
                    className="settlement-mobile-record-button"
                    type="button"
                    aria-expanded={selectedId === record.id}
                    onClick={() => setSelectedId(selectedId === record.id ? null : record.id)}
                  >
                    <span className="settlement-mobile-record-head">
                      <code title={record.payment_id}>{shortId(record.payment_id)}</code>
                      <StatusBadge
                        status={record.reconciliation_status}
                        label={labelForStatus(record.reconciliation_status)}
                      />
                    </span>
                    <span className="settlement-mobile-record-meta">
                      <span>{labelForStatus(record.payment_state)}</span>
                      <span>{displayTime(record.last_checked_at)}</span>
                    </span>
                    <span className="settlement-mobile-record-action">
                      {selectedId === record.id ? "Hide evidence" : "Inspect evidence"}
                    </span>
                  </button>
                </article>
              ))}
            </div>

            {selectedRecord ? <ReviewFacts record={selectedRecord} /> : null}

            <footer className="settlement-pagination">
              <span>Page {pageIndex + 1}</span>
              <div>
                <button
                  className="button"
                  type="button"
                  onClick={previousPage}
                  disabled={pageIndex === 0 || query.isFetching}
                >
                  Previous
                </button>
                <button
                  className="button"
                  type="button"
                  onClick={nextPage}
                  disabled={!hasNext || query.isFetching}
                >
                  Next
                </button>
              </div>
            </footer>
          </>
        )}
        {token && pageIndex > 0 && (query.isError || (query.isSuccess && items.length === 0)) ? (
          <footer className="settlement-pagination">
            <span>Page {pageIndex + 1}</span>
            <button
              className="button"
              type="button"
              onClick={previousPage}
              disabled={query.isFetching}
            >
              Previous
            </button>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
