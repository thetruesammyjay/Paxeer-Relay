"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import {
  createApiKey,
  revokeApiKey,
  useApiKeys,
} from "@/hooks/use-api-keys";
import type { ApiKeyRecord } from "@/hooks/use-api-keys";
import { ApiError } from "@/lib/api-client";

const AVAILABLE_SCOPES = [
  "agents:read",
  "agents:write",
  "providers:read",
  "providers:write",
  "services:read",
  "services:write",
  "policies:read",
  "policies:write",
  "approvals:read",
  "approvals:write",
  "api-keys:read",
  "api-keys:write",
  "receipts:read",
  "transactions:read",
  "settlements:read",
  "analytics:read",
  "audit-logs:read",
  "webhooks:read",
  "webhooks:write",
  "batch:write",
  "project-members:read",
  "gateway:invoke",
] as const;

type KeyStatus = "active" | "expired" | "revoked";

function parseApiDate(value: string) {
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
}

function keyStatus(key: ApiKeyRecord, now: number): KeyStatus {
  if (!key.is_active) return "revoked";
  if (now && key.expires_at) {
    const expiration = parseApiDate(key.expires_at).getTime();
    if (Number.isFinite(expiration) && expiration <= now) return "expired";
  }
  return "active";
}

function formatDate(value: string | null) {
  if (!value) return "Never";
  const date = parseApiDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function scopeItems(value: string) {
  const parts = value.split(":");
  const scopes: string[] = [];
  for (let index = 0; index < parts.length - 1; index += 2) {
    scopes.push(`${parts[index]}:${parts[index + 1]}`);
  }
  return scopes;
}

function keyMatches(key: ApiKeyRecord, search: string) {
  return [key.name, key.key_prefix, key.key_type, key.scopes, key.id]
    .some((value) => value.toLowerCase().includes(search));
}

function requestErrorMessage(
  error: unknown,
  action: "load" | "create" | "revoke",
) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) {
      if (action === "load") {
        return "Your current project access needs api-keys:read permission to view the inventory.";
      }
      if (action === "revoke") {
        return "Your current project access needs api-keys:write permission to revoke keys.";
      }
      return "Your current project access cannot create a key with one or more selected permissions.";
    }
    if (error.status === 404 && action === "revoke") {
      return "That API key was not found in this project and environment. Refresh the list and try again.";
    }
    if (error.status === 422) {
      return "The request is invalid. Check the key name, key type, expiry, and selected permissions.";
    }
    return `The API key request failed (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

export function ApiKeyInventory() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [connectionId, setConnectionId] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [keyName, setKeyName] = useState("");
  const [keyType, setKeyType] = useState<"" | "test" | "live">("");
  const [expiresInDays, setExpiresInDays] = useState("90");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [createdSecret, setCreatedSecret] = useState("");
  const [createdSecretNotice, setCreatedSecretNotice] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState("");
  const [confirmingRevokeId, setConfirmingRevokeId] = useState("");
  const [revokingId, setRevokingId] = useState("");
  const [revokeError, setRevokeError] = useState("");
  const [now, setNow] = useState(0);
  const query = useApiKeys(apiKey, connectionId);

  useEffect(() => {
    setNow(Date.now());
  }, [query.dataUpdatedAt]);

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({ queryKey: ["api-keys", activeConnectionId] });
      }
    };
  }, [connectionId, queryClient]);

  function connect(key: string) {
    setApiKey(key);
    setConnectionId(globalThis.crypto.randomUUID());
    setCreatedSecret("");
  }

  function disconnect() {
    if (connectionId) {
      queryClient.removeQueries({ queryKey: ["api-keys", connectionId] });
    }
    setApiKey("");
    setConnectionId("");
    setSearch("");
    setStatusFilter("");
    setKeyName("");
    setKeyType("");
    setExpiresInDays("90");
    setSelectedScopes([]);
    setCreatedSecret("");
    setCreatedSecretNotice("");
    setCreateError("");
    setConfirmingRevokeId("");
    setRevokeError("");
  }

  const currentKeyRecord = query.data?.find((key) =>
    apiKey.startsWith(key.key_prefix),
  );
  const availableKeyType =
    currentKeyRecord?.key_type ?? query.data?.[0]?.key_type;
  useEffect(() => {
    if (availableKeyType) setKeyType((current) => current || availableKeyType);
  }, [availableKeyType]);
  const currentKeyScopes = currentKeyRecord
    ? new Set(scopeItems(currentKeyRecord.scopes))
    : null;
  // The inventory is capped at 100 rows, so an older connected key may not
  // appear in it. In that case let the API confirm write access instead of
  // incorrectly hiding management controls.
  const canManageKeys =
    !currentKeyRecord || currentKeyScopes?.has("api-keys:write") === true;
  const visibleScopes = currentKeyScopes
    ? AVAILABLE_SCOPES.filter((scope) => currentKeyScopes.has(scope))
    : AVAILABLE_SCOPES;

  const normalizedSearch = search.trim().toLowerCase();
  const keys = useMemo(
    () =>
      (query.data ?? []).filter((key) => {
        const status = keyStatus(key, now);
        return (
          (!statusFilter || status === statusFilter) &&
          keyMatches(key, normalizedSearch)
        );
      }),
    [query.data, now, statusFilter, normalizedSearch],
  );
  const hasFilters = Boolean(normalizedSearch || statusFilter);
  const expiresDaysNumber = Number(expiresInDays);
  const canCreate = Boolean(
    keyName.trim() &&
      keyType &&
      selectedScopes.length &&
      Number.isInteger(expiresDaysNumber) &&
      expiresDaysNumber >= 1 &&
      expiresDaysNumber <= 365,
  );

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate || !keyType) return;
    setCreateBusy(true);
    setCreateError("");
    setCreatedSecret("");
    setCreatedSecretNotice("");
    try {
      const created = await createApiKey(apiKey, {
        name: keyName.trim(),
        key_type: keyType,
        scopes: selectedScopes.join(":"),
        expires_in_days: expiresDaysNumber,
      });
      setCreatedSecret(created.raw_key ?? "");
      if (!created.raw_key) {
        setCreatedSecretNotice(
          "The API created the key but did not return its one-time secret.",
        );
      }
      setKeyName("");
      setSelectedScopes([]);
      await queryClient.invalidateQueries({
        queryKey: ["api-keys", connectionId],
      });
    } catch (error) {
      setCreateError(requestErrorMessage(error, "create"));
    } finally {
      setCreateBusy(false);
    }
  }

  async function handleRevoke(keyId: string) {
    setRevokingId(keyId);
    setRevokeError("");
    try {
      await revokeApiKey(apiKey, keyId);
      setConfirmingRevokeId("");
      await queryClient.invalidateQueries({
        queryKey: ["api-keys", connectionId],
      });
    } catch (error) {
      setRevokeError(requestErrorMessage(error, "revoke"));
    } finally {
      setRevokingId("");
    }
  }

  async function copyCreatedSecret() {
    try {
      await navigator.clipboard.writeText(createdSecret);
      setCreatedSecretNotice(
        "Copied. Save the key somewhere secure; it is shown only once.",
      );
    } catch {
      setCreatedSecretNotice(
        "Copy is unavailable here. Select and copy the key now; it is shown only once.",
      );
    }
  }

  function toggleScope(scope: string) {
    setSelectedScopes((current) =>
      current.includes(scope)
        ? current.filter((item) => item !== scope)
        : [...current, scope],
    );
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Workspace security</div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">
            Review access keys for this project and environment, and issue or
            revoke keys with clear permission boundaries.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh keys"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="api-keys:read"
        title="Connect to the project key inventory"
        actionLabel="Load API keys"
        apiKey={apiKey}
        connected={query.isSuccess && !query.isError}
        loading={query.isFetching || createBusy || Boolean(revokingId)}
        error={query.isError ? requestErrorMessage(query.error, "load") : ""}
        onConnect={connect}
        onDisconnect={disconnect}
      />

      {!apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">
            AK
          </div>
          <div>
            <h2>Project access keys will appear here</h2>
            <p>
              Connect to a workspace with <code>api-keys:read</code> access to review the
              inventory. Creating and revoking keys also requires
              <code> api-keys:write</code>. Secrets are never shown in the
              inventory.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading API key inventory</h2>
            <p>The key permissions and project access are being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>API key inventory is unavailable</h2>
            <p>{requestErrorMessage(query.error, "load")}</p>
          </div>
          <button
            className="button"
            type="button"
            onClick={() => void query.refetch()}
          >
            Try again
          </button>
        </section>
      ) : (
        <>
          {createdSecret ? (
            <section className="card api-key-secret" role="status">
              <div className="eyebrow">One-time key</div>
              <h2>Copy and store this API key now</h2>
              <p>
                The raw key will not appear in the inventory or be returned
                again.
              </p>
              <code>{createdSecret}</code>
              <div className="page-actions">
                <button
                  className="button primary"
                  type="button"
                  onClick={() => void copyCreatedSecret()}
                >
                  Copy key
                </button>
                <button
                  className="button"
                  type="button"
                  onClick={() => {
                    setCreatedSecret("");
                    setCreatedSecretNotice("");
                  }}
                >
                  I saved the key
                </button>
              </div>
              {createdSecretNotice ? (
                <p aria-live="polite">{createdSecretNotice}</p>
              ) : null}
            </section>
          ) : null}
          {createdSecretNotice && !createdSecret ? (
            <p className="form-error" role="status">
              {createdSecretNotice}
            </p>
          ) : null}

          {canManageKeys ? (
            <section className="card api-key-create-card">
              <header className="card-head">
                <div>
                  <h2 className="card-title">Create an API key</h2>
                  <p className="card-description">
                    Choose only the permissions this integration needs. The API
                    limits new key permissions to those granted to your current
                    project access.
                  </p>
                </div>
              </header>
              <form className="api-key-create-form" onSubmit={handleCreate}>
                <label className="scoped-key-field">
                  <span>Key name</span>
                  <input
                    className="search"
                    required
                    maxLength={128}
                    value={keyName}
                    onChange={(event) => setKeyName(event.target.value)}
                    placeholder="e.g. staging analytics job"
                  />
                </label>
                <label className="scoped-key-field">
                  <span>Key type / environment</span>
                  <select
                    className="search"
                    required
                    value={keyType}
                    onChange={(event) =>
                      setKeyType(event.target.value as "" | "test" | "live")
                    }
                  >
                    <option value="">Select project environment</option>
                    <option value="test">Test (development or staging)</option>
                    <option value="live">Live (production)</option>
                  </select>
                </label>
                <label className="scoped-key-field">
                  <span>Expires in days</span>
                  <input
                    className="search"
                    type="number"
                    min={1}
                    max={365}
                    step={1}
                    required
                    value={expiresInDays}
                    onChange={(event) => setExpiresInDays(event.target.value)}
                  />
                </label>
                <fieldset className="api-key-scopes">
                  <legend>Permissions</legend>
                  <details className="api-key-scope-picker">
                    <summary>
                      Choose permissions · {selectedScopes.length} selected
                    </summary>
                    <div className="api-key-scope-grid">
                      {visibleScopes.map((scope) => (
                        <label key={scope}>
                          <input
                            type="checkbox"
                            checked={selectedScopes.includes(scope)}
                            onChange={() => toggleScope(scope)}
                          />
                          <code>{scope}</code>
                        </label>
                      ))}
                    </div>
                    <p>
                      A new key cannot receive permissions your current role
                      does not hold. The API also checks that the selected type
                      matches the project environment.
                    </p>
                  </details>
                </fieldset>
                {createError ? (
                  <p className="form-error" role="alert">
                    {createError}
                  </p>
                ) : null}
                <div className="page-actions">
                  <button
                    className="button primary"
                    type="submit"
                    disabled={!canCreate || createBusy}
                  >
                    {createBusy ? "Creating key…" : "Create key"}
                  </button>
                </div>
              </form>
            </section>
          ) : (
            <section className="card data-access-empty" role="note">
              <h3>Read-only key access</h3>
              <p>
                Your role can review the inventory. Ask an owner to grant
                <code> api-keys:write</code> to create or revoke keys.
              </p>
            </section>
          )}

          <div className="transaction-toolbar toolbar">
            <input
              className="search"
              type="search"
              aria-label="Search API keys"
              placeholder="Search key name, prefix, or permission"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Status</span>
              <select
                className="search transaction-filter"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                aria-label="Filter API keys by status"
              >
                <option value="">All keys</option>
                <option value="active">Active</option>
                <option value="expired">Expired</option>
                <option value="revoked">Revoked</option>
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {keys.length} shown · up to 100 recent keys
            </span>
          </div>

          {revokeError ? (
            <p className="form-error" role="alert">
              {revokeError}
            </p>
          ) : null}
          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">API key inventory</h2>
                <p className="card-description">
                  The inventory contains metadata only. Use a separate key
                  with <code>api-keys:write</code> to manage access if this key
                  is read-only.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>
            {keys.length === 0 ? (
              <div className="data-access-empty">
                <h3>{hasFilters ? "No matching API keys" : "No API keys found"}</h3>
                <p>
                  {hasFilters
                    ? "Try another search or status filter."
                    : "Create a scoped key for an integration that needs project access."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table api-key-table">
                  <thead>
                    <tr>
                      <th scope="col">Key</th>
                      <th scope="col">Type</th>
                      <th scope="col">Permissions</th>
                      <th scope="col">Created</th>
                      <th scope="col">Last used</th>
                      <th scope="col">Expires</th>
                      <th scope="col">Status</th>
                      <th scope="col">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((key) => {
                      const status = keyStatus(key, now);
                      const isCurrentKey = apiKey.startsWith(key.key_prefix);
                      return (
                        <tr key={key.id}>
                          <td>
                            <div className="cell-stack">
                              <strong>{key.name}</strong>
                              <code className="mono" title={key.key_prefix}>
                                {key.key_prefix}…
                              </code>
                            </div>
                          </td>
                          <td>
                            <span className="status neutral">{key.key_type}</span>
                          </td>
                          <td>
                            <div className="api-key-scope-tags">
                              {scopeItems(key.scopes).map((scope) => (
                                <code key={scope}>{scope}</code>
                              ))}
                            </div>
                          </td>
                          <td>{formatDate(key.created_at)}</td>
                          <td>{formatDate(key.last_used_at)}</td>
                          <td>{formatDate(key.expires_at)}</td>
                          <td>
                            <span
                              className={`status ${status === "active" ? "active" : status === "expired" ? "pending" : "denied"}`}
                            >
                              {status}
                            </span>
                          </td>
                          <td>
                            {!key.is_active ? (
                              <span className="muted">Revoked</span>
                            ) : isCurrentKey ? (
                              <span
                                className="muted"
                                title="Change to a different key before revoking this one"
                              >
                                Current key
                              </span>
                            ) : !canManageKeys ? (
                              <span className="muted">Read-only</span>
                            ) : confirmingRevokeId === key.id ? (
                              <div className="api-key-revoke-confirm">
                                <span>
                                  Revoke “{key.name}” immediately? Its access
                                  stops now.
                                </span>
                                <button
                                  className="button danger"
                                  type="button"
                                  disabled={revokingId === key.id}
                                  aria-label={`Confirm immediate revocation of ${key.name}`}
                                  onClick={() => void handleRevoke(key.id)}
                                >
                                  {revokingId === key.id ? "Revoking…" : "Confirm revoke"}
                                </button>
                                <button
                                  className="button ghost"
                                  type="button"
                                  disabled={revokingId === key.id}
                                  onClick={() => setConfirmingRevokeId("")}
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                className="button ghost"
                                type="button"
                                onClick={() => {
                                  setRevokeError("");
                                  setConfirmingRevokeId(key.id);
                                }}
                              >
                                Revoke
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
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
