"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import { ProviderCreateForm } from "@/components/provider-create-form";
import { useProviders } from "@/hooks/use-providers";
import type { ProviderRecord } from "@/hooks/use-providers";
import { ApiError } from "@/lib/api-client";

const PROVIDER_STATUSES = ["active", "inactive", "suspended"] as const;

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function statusTone(status: string) {
  if (status === "active") return "active";
  if (status === "suspended") return "denied";
  if (status === "inactive") return "paused";
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

function displayWallet(value: string | null) {
  if (!value) return "No wallet configured";
  return `${value.slice(0, 6)}…${value.slice(-4)}`;
}

function safeWebsite(value: string | null) {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return { href: url.href, label: url.hostname };
  } catch {
    return null;
  }
}

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) {
      return "Your current project access needs providers:read permission.";
    }
    if (error.status === 404) {
      return "The providers endpoint was not found. Update the API and try again.";
    }
    return `Providers could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function matchesVerified(provider: ProviderRecord, filter: string) {
  if (filter === "verified") return provider.is_verified;
  if (filter === "unverified") return !provider.is_verified;
  return true;
}

export function ProviderDirectory() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [keyValidated, setKeyValidated] = useState(false);
  const [connectionId, setConnectionId] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("");
  const [verification, setVerification] = useState("");
  const [copiedProviderId, setCopiedProviderId] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const [copyFallbackId, setCopyFallbackId] = useState("");
  const filters = { search: debouncedSearch, status };
  const query = useProviders(apiKey, connectionId, filters);

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
          queryKey: ["providers", activeConnectionId],
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
      queryClient.removeQueries({ queryKey: ["providers", connectionId] });
    }
    setApiKey("");
    setKeyValidated(false);
    setConnectionId("");
    setSearch("");
    setDebouncedSearch("");
    setStatus("");
    setVerification("");
    setCopiedProviderId("");
    setCopyMessage("");
    setCopyFallbackId("");
  }

  function handleCreated() {
    void queryClient.invalidateQueries({
      queryKey: ["providers", connectionId],
    });
  }

  async function copyProviderId(providerId: string) {
    setCopyMessage("");
    setCopyFallbackId("");
    try {
      await navigator.clipboard.writeText(providerId);
      setCopiedProviderId(providerId);
      setCopyMessage("Provider ID copied to clipboard.");
    } catch {
      setCopiedProviderId("");
      setCopyFallbackId(providerId);
      setCopyMessage("Clipboard access is unavailable. Copy this ID manually:");
    }
  }

  const providers = useMemo(
    () =>
      (query.data ?? []).filter((provider) =>
        matchesVerified(provider, verification),
      ),
    [query.data, verification],
  );
  const hasFilters = Boolean(search.trim() || status || verification);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Service network</div>
          <h1 className="page-title">Providers</h1>
          <p className="page-subtitle">
            Review providers registered to this project and environment.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh providers"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="providers:read"
        actionLabel="Load providers"
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
            PR
          </div>
          <div>
            <h2>Your providers will appear here</h2>
            <p>
              Connect to a workspace to see provider records registered to the
              selected project and environment. No sample providers are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading provider directory</h2>
            <p>Your project access is being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Provider directory is unavailable</h2>
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
          <ProviderCreateForm apiKey={apiKey} onCreated={handleCreated} />
          <div className="transaction-toolbar toolbar">
            <input
              className="search"
              type="search"
              aria-label="Search providers by name or slug"
              placeholder="Search provider name or slug"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Status</span>
              <select
                className="search transaction-filter"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                aria-label="Filter by provider status"
              >
                <option value="">All statuses</option>
                {PROVIDER_STATUSES.map((providerStatus) => (
                  <option key={providerStatus} value={providerStatus}>
                    {providerStatus.charAt(0).toUpperCase() + providerStatus.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <label className="transaction-filter-label">
              <span>Verification</span>
              <select
                className="search transaction-filter"
                value={verification}
                onChange={(event) => setVerification(event.target.value)}
                aria-label="Filter by verification status"
              >
                <option value="">All providers</option>
                <option value="verified">Verified</option>
                <option value="unverified">Unverified</option>
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {providers.length} shown · up to 100 recent records
            </span>
          </div>

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">Registered providers</h2>
                <p className="card-description">
                  Refreshes every 30 seconds. Provider records do not include
                  live service health or performance metrics.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {providers.length === 0 ? (
              <div className="data-access-empty">
                <h3>{hasFilters ? "No matching providers" : "No providers found"}</h3>
                <p>
                  {hasFilters
                    ? "Try another search or select different filters."
                    : "Providers registered to this project will appear here."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table provider-directory-table">
                  <thead>
                    <tr>
                      <th scope="col">Provider</th>
                      <th scope="col">Provider ID</th>
                      <th scope="col">Wallet</th>
                      <th scope="col">Environment</th>
                      <th scope="col">Verification</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {providers.map((provider, index) => {
                      const website = safeWebsite(provider.website_url);
                      return (
                        <tr key={provider.id}>
                          <td>
                            <div className="agent-cell">
                              <span
                                className={`agent-avatar ${index % 3 === 0 ? "orange" : index % 3 === 1 ? "green" : "blue"}`}
                                aria-hidden="true"
                              >
                                {initials(provider.name)}
                              </span>
                              <div className="cell-stack">
                                <strong>{provider.name}</strong>
                                <span>{provider.slug}</span>
                                {website ? (
                                  <a
                                    className="provider-website"
                                    href={website.href}
                                    aria-label={`Open provider website ${website.label} in a new tab`}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {website.label}
                                  </a>
                                ) : null}
                              </div>
                            </div>
                          </td>
                          <td>
                            <div className="agent-id-cell">
                              <code className="primary-cell mono" title={provider.id}>
                                {shortId(provider.id)}
                              </code>
                              <button
                                className="button ghost agent-copy-id"
                                type="button"
                                aria-label={`Copy provider ID ${provider.id}`}
                                onClick={() => void copyProviderId(provider.id)}
                              >
                                {copiedProviderId === provider.id ? "Copied" : "Copy ID"}
                              </button>
                            </div>
                          </td>
                          <td>
                            <div className="provider-payment-destinations">
                              {provider.wallet_address ? (
                                <code className="mono" title={provider.wallet_address}>
                                  EVM {displayWallet(provider.wallet_address)}
                                </code>
                              ) : null}
                              {provider.layerx_account_id ? (
                                <code className="mono" title={provider.layerx_account_id}>
                                  LayerX {provider.layerx_account_id.slice(0, 10)}…{provider.layerx_account_id.slice(-8)}
                                </code>
                              ) : null}
                              {!provider.wallet_address && !provider.layerx_account_id ? (
                                <span className="muted">No payment destination configured</span>
                              ) : null}
                            </div>
                          </td>
                          <td>{provider.environment}</td>
                          <td>
                            <span className={`status ${provider.is_verified ? "verified" : "neutral"}`}>
                              {provider.is_verified ? "Verified" : "Unverified"}
                            </span>
                          </td>
                          <td>
                            <span className={`status ${statusTone(provider.status)}`}>
                              {provider.status.charAt(0).toUpperCase() + provider.status.slice(1)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {copyMessage ? (
              <p className="agent-copy-feedback" role="status" aria-live="polite">
                {copyMessage} {copyFallbackId ? <code className="mono">{copyFallbackId}</code> : null}
              </p>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}
