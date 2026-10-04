"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import { useAgents } from "@/hooks/use-agents";
import type { Agent } from "@/hooks/use-agents";
import { ApiError } from "@/lib/api-client";

const AGENT_STATUSES = ["active", "paused", "revoked"];

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

function displayWallet(value: string | null) {
  if (!value) return "No wallet linked";
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "The API key was not accepted. Check it and try again.";
    if (error.status === 403) {
      return "This key needs agents:read access for this project and environment.";
    }
    if (error.status === 404) {
      return "The agents endpoint was not found. Update the API and try again.";
    }
    return `Agents could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function matchesSearch(agent: Agent, query: string) {
  return [
    agent.id,
    agent.name,
    agent.slug,
    agent.status,
    agent.wallet_address ?? "",
    agent.description ?? "",
  ].some((value) => value.toLowerCase().includes(query));
}

function statusTone(status: string) {
  if (status === "active") return "active";
  if (status === "paused") return "paused";
  if (status === "revoked") return "denied";
  return "neutral";
}

function initials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function AgentDirectory() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const query = useAgents(apiKey, connectionId);

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({ queryKey: ["agents", activeConnectionId] });
      }
    };
  }, [connectionId, queryClient]);

  function connect(key: string) {
    setApiKey(key);
    setConnectionId(globalThis.crypto.randomUUID());
  }

  function disconnect() {
    if (connectionId) {
      queryClient.removeQueries({ queryKey: ["agents", connectionId] });
    }
    setApiKey("");
    setConnectionId("");
    setStatus("");
    setSearch("");
  }

  const normalizedSearch = search.trim().toLowerCase();
  const hasFilters = Boolean(normalizedSearch || status);
  const agents = useMemo(
    () =>
      (query.data ?? []).filter(
        (agent) =>
          (!status || agent.status === status) &&
          matchesSearch(agent, normalizedSearch),
      ),
    [query.data, status, normalizedSearch],
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Autonomous operators</div>
          <h1 className="page-title">Agents</h1>
          <p className="page-subtitle">
            Review registered agents, their wallet links, and whether each one
            can operate.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh agents"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="agents:read"
        actionLabel="Load agents"
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
            AG
          </div>
          <div>
            <h2>Your agents will appear here</h2>
            <p>
              Connect a key to see agents registered to its project and
              environment. No sample agents are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading agent directory</h2>
            <p>The API key and project access are being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Agent directory is unavailable</h2>
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
              aria-label="Search agents"
              placeholder="Search name, ID, or wallet"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Status</span>
              <select
                className="search transaction-filter"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                aria-label="Filter by agent status"
              >
                <option value="">All statuses</option>
                {AGENT_STATUSES.map((agentStatus) => (
                  <option key={agentStatus} value={agentStatus}>
                    {agentStatus.charAt(0).toUpperCase() + agentStatus.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {agents.length} shown · up to 100 recent records
            </span>
          </div>

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">Registered agents</h2>
                <p className="card-description">
                  Refreshes every 30 seconds while this page is active.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {agents.length === 0 ? (
              <div className="data-access-empty">
                <h3>{hasFilters ? "No matching agents" : "No agents found"}</h3>
                <p>
                  {hasFilters
                    ? "Try another search or select a different status."
                    : "Agents registered to this project will appear here."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table agent-directory-table">
                  <thead>
                    <tr>
                      <th scope="col">Agent</th>
                      <th scope="col">Agent ID</th>
                      <th scope="col">Wallet</th>
                      <th scope="col">Environment</th>
                      <th scope="col">Created</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((agent, index) => (
                      <tr key={agent.id}>
                        <td>
                          <div className="agent-cell">
                            <span
                              className={`agent-avatar ${index % 3 === 0 ? "orange" : index % 3 === 1 ? "green" : "blue"}`}
                              aria-hidden="true"
                            >
                              {initials(agent.name)}
                            </span>
                            <div className="cell-stack">
                              <strong>{agent.name}</strong>
                              <span>{agent.slug}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <code className="primary-cell mono" title={agent.id}>
                            {shortId(agent.id)}
                          </code>
                        </td>
                        <td>
                          {agent.wallet_address ? (
                            <code
                              className="mono"
                              title={agent.wallet_address}
                            >
                              {displayWallet(agent.wallet_address)}
                            </code>
                          ) : (
                            <span className="muted">No wallet linked</span>
                          )}
                        </td>
                        <td>{agent.environment}</td>
                        <td className="transaction-date">
                          {displayDate(agent.created_at)}
                        </td>
                        <td>
                          <span className={`status ${statusTone(agent.status)}`}>
                            {agent.status.charAt(0).toUpperCase() +
                              agent.status.slice(1)}
                          </span>
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
