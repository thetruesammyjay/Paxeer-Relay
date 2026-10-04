"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import { usePolicies } from "@/hooks/use-policies";
import { ApiError } from "@/lib/api-client";

const POLICY_MODES = ["observe", "warn", "enforce"] as const;

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "The API key was not accepted. Check it and try again.";
    if (error.status === 403) {
      return "This key needs policies:read access for this project and environment.";
    }
    if (error.status === 404) {
      return "The policies endpoint was not found. Update the API and try again.";
    }
    return `Policies could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function titleCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function PolicyDirectory() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [keyValidated, setKeyValidated] = useState(false);
  const [connectionId, setConnectionId] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [mode, setMode] = useState("");
  const [active, setActive] = useState("");
  const filters = { search: debouncedSearch, mode, active };
  const query = usePolicies(apiKey, connectionId, filters);

  useEffect(() => {
    if (query.isSuccess) setKeyValidated(true);
    if (query.isError) setKeyValidated(false);
  }, [query.isError, query.isSuccess]);

  useEffect(() => {
    const timeoutId = window.setTimeout(
      () => setDebouncedSearch(search.trim()),
      250,
    );
    return () => window.clearTimeout(timeoutId);
  }, [search]);

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({
          queryKey: ["policies", activeConnectionId],
        });
      }
    };
  }, [connectionId, queryClient]);

  function connect(key: string) {
    setApiKey(key);
    setKeyValidated(false);
    setConnectionId(globalThis.crypto.randomUUID());
  }

  function disconnect() {
    if (connectionId) {
      queryClient.removeQueries({ queryKey: ["policies", connectionId] });
    }
    setApiKey("");
    setKeyValidated(false);
    setConnectionId("");
    setSearch("");
    setDebouncedSearch("");
    setMode("");
    setActive("");
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Deterministic controls</div>
          <h1 className="page-title">Policies</h1>
          <p className="page-subtitle">
            Review the spending rules registered for this project and
            environment.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh policies"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="policies:read"
        actionLabel="Load policies"
        apiKey={apiKey}
        connected={keyValidated && !query.isError}
        loading={query.isFetching}
        error={query.isError ? keyErrorMessage(query.error) : ""}
        onConnect={connect}
        onDisconnect={disconnect}
      />

      {!apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">
            PL
          </div>
          <div>
            <h2>Your policies will appear here</h2>
            <p>
              Connect a key to see policies registered to its project and
              environment. No sample policies are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading policy directory</h2>
            <p>The API key and project access are being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Policy directory is unavailable</h2>
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
              aria-label="Search policies by name"
              placeholder="Search policy names"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Mode</span>
              <select
                className="search transaction-filter"
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                aria-label="Filter by policy mode"
              >
                <option value="">All modes</option>
                {POLICY_MODES.map((policyMode) => (
                  <option key={policyMode} value={policyMode}>
                    {titleCase(policyMode)}
                  </option>
                ))}
              </select>
            </label>
            <label className="transaction-filter-label">
              <span>Availability</span>
              <select
                className="search transaction-filter"
                value={active}
                onChange={(event) => setActive(event.target.value)}
                aria-label="Filter by policy availability"
              >
                <option value="">All policies</option>
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {query.data?.length ?? 0} policies · up to 100 results
            </span>
          </div>

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">Policy summaries</h2>
                <p className="card-description">
                  Refreshes every 30 seconds. This API view does not include
                  rule details or agent assignments.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {query.data?.length === 0 ? (
              <div className="data-access-empty">
                <h3>
                  {search.trim() || mode || active
                    ? "No matching policies"
                    : "No policies found"}
                </h3>
                <p>
                  {search.trim() || mode || active
                    ? "Try another name, mode, or availability filter."
                    : "Policies registered to this project will appear here."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table policy-directory-table">
                  <thead>
                    <tr>
                      <th scope="col">Policy</th>
                      <th scope="col">Policy ID</th>
                      <th scope="col">Mode</th>
                      <th scope="col">Version</th>
                      <th scope="col">Availability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(query.data ?? []).map((policy) => (
                      <tr key={policy.id}>
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
                            {titleCase(policy.mode)}
                          </span>
                        </td>
                        <td className="primary-cell">v{policy.version}</td>
                        <td>
                          <span
                            className={`status ${policy.is_active ? "active" : "neutral"}`}
                          >
                            {policy.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div className="detail-grid" style={{ marginTop: 14 }}>
            <div className="card detail-card">
              <div className="eyebrow">Observe</div>
              <strong>Record violations</strong>
              <p>Requests continue while the policy records rule violations.</p>
            </div>
            <div className="card detail-card">
              <div className="eyebrow">Warn</div>
              <strong>Permit and alert</strong>
              <p>Requests can continue while policy violations raise alerts.</p>
            </div>
            <div className="card detail-card">
              <div className="eyebrow">Enforce</div>
              <strong>Apply the boundary</strong>
              <p>Requests that break enforced rules are blocked.</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
