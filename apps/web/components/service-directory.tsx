"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";
import { ServicePublishForm } from "@/components/service-publish-form";
import { ServiceStatusControl } from "@/components/service-status-control";
import { useServices } from "@/hooks/use-services";
import type { ServiceRecord } from "@/hooks/use-services";
import { ApiError } from "@/lib/api-client";

const SERVICE_STATUSES = ["active", "inactive", "deprecated"] as const;
const SERVICE_PROTOCOLS = ["http", "mcp", "grpc"] as const;

function shortId(value: string) {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function displayPrice(service: ServiceRecord) {
  const price = service.price_per_call;
  if (!price) return "Price not set";
  if (
    !/^\d+$/.test(price.amount_atomic) ||
    !Number.isInteger(price.decimals) ||
    price.decimals < 0 ||
    price.decimals > 30
  ) {
    return `${price.amount_atomic} atomic ${price.currency}`;
  }

  const amount = BigInt(price.amount_atomic);
  const scale = 10n ** BigInt(price.decimals);
  const whole = amount / scale;
  if (price.decimals === 0) return `${whole.toLocaleString()} ${price.currency}`;

  const fraction = (amount % scale)
    .toString()
    .padStart(price.decimals, "0")
    .replace(/0+$/, "");
  return `${whole.toLocaleString()}${fraction ? `.${fraction}` : ""} ${price.currency}`;
}

function statusTone(status: string) {
  if (status === "active") return "active";
  if (status === "deprecated") return "denied";
  if (status === "inactive") return "paused";
  return "neutral";
}

function statusLabel(status: string) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function probeStatus(health: ServiceRecord["health"]) {
  if (!health.last_check_at) return "Awaiting first probe";
  if (health.last_check_passing) return "Last probe passed";
  return "Last probe failed";
}

function probeTone(health: ServiceRecord["health"]) {
  if (!health.last_check_at) return "neutral";
  return health.last_check_passing ? "active" : "denied";
}

function probeTime(health: ServiceRecord["health"]) {
  if (!health.last_check_at) return "Not measured yet";
  const checkedAt = new Date(health.last_check_at);
  if (Number.isNaN(checkedAt.getTime())) return "Check time unavailable";
  return `Checked ${checkedAt.toLocaleString()}`;
}

function keyErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) {
      return "Your current project access needs services:read permission.";
    }
    if (error.status === 404) {
      return "The services endpoint was not found. Update the API and try again.";
    }
    return `Services could not be loaded (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

function matchesSearch(service: ServiceRecord, search: string) {
  return [
    service.id,
    service.provider_id,
    service.name,
    service.slug,
    service.capability,
    service.status,
    service.description ?? "",
    ...service.protocols,
  ].some((value) => value.toLowerCase().includes(search));
}

export function ServiceDirectory() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [keyValidated, setKeyValidated] = useState(false);
  const [connectionId, setConnectionId] = useState("");
  const [status, setStatus] = useState("");
  const [protocol, setProtocol] = useState("");
  const [search, setSearch] = useState("");
  const query = useServices(apiKey, connectionId);

  useEffect(() => {
    if (query.isSuccess) setKeyValidated(true);
    if (query.isError) setKeyValidated(false);
  }, [query.isError, query.isSuccess]);

  useEffect(() => {
    const activeConnectionId = connectionId;
    return () => {
      if (activeConnectionId) {
        queryClient.removeQueries({
          queryKey: ["services", activeConnectionId],
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
      queryClient.removeQueries({ queryKey: ["services", connectionId] });
    }
    setApiKey("");
    setKeyValidated(false);
    setConnectionId("");
    setStatus("");
    setProtocol("");
    setSearch("");
  }

  function handlePublished() {
    void queryClient.invalidateQueries({
      queryKey: ["services", connectionId],
    });
  }

  const normalizedSearch = search.trim().toLowerCase();
  const hasFilters = Boolean(normalizedSearch || status || protocol);
  const services = useMemo(
    () =>
      (query.data ?? []).filter(
        (service) =>
          (!status || service.status === status) &&
          (!protocol || service.protocols.includes(protocol)) &&
          matchesSearch(service, normalizedSearch),
      ),
    [query.data, status, protocol, normalizedSearch],
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Paid capabilities</div>
          <h1 className="page-title">Services</h1>
          <p className="page-subtitle">
            Review published capabilities, per-call prices, and the latest
            provider health checks.
          </p>
        </div>
        {apiKey ? (
          <button
            className="button primary"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "Refreshing…" : "Refresh services"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="services:read"
        actionLabel="Load services"
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
            SV
          </div>
          <div>
            <h2>Your services will appear here</h2>
            <p>
              Connect to a workspace to see services registered to the selected
              project and environment. No sample services are shown.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading service directory</h2>
            <p>Your project access is being checked.</p>
          </div>
        </section>
      ) : query.isError ? (
        <section className="card data-access-placeholder" role="alert">
          <div>
            <h2>Service directory is unavailable</h2>
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
          <ServicePublishForm apiKey={apiKey} onPublished={handlePublished} />
          <div className="transaction-toolbar toolbar">
            <input
              className="search"
              type="search"
              aria-label="Search services"
              placeholder="Search service, capability, or provider ID"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <label className="transaction-filter-label">
              <span>Status</span>
              <select
                className="search transaction-filter"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                aria-label="Filter by service status"
              >
                <option value="">All statuses</option>
                {SERVICE_STATUSES.map((serviceStatus) => (
                  <option key={serviceStatus} value={serviceStatus}>
                    {statusLabel(serviceStatus)}
                  </option>
                ))}
              </select>
            </label>
            <label className="transaction-filter-label">
              <span>Protocol</span>
              <select
                className="search transaction-filter"
                value={protocol}
                onChange={(event) => setProtocol(event.target.value)}
                aria-label="Filter by protocol"
              >
                <option value="">All protocols</option>
                {SERVICE_PROTOCOLS.map((serviceProtocol) => (
                  <option key={serviceProtocol} value={serviceProtocol}>
                    {serviceProtocol.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
            <span className="card-meta" aria-live="polite">
              {services.length} shown · up to 100 recent records
            </span>
          </div>

          <section className="card">
            <header className="card-head">
              <div>
                <h2 className="card-title">Published services</h2>
                <p className="card-description">
                  Refreshes every 30 seconds. New services remain out of
                  routing until the first health probe passes.
                </p>
              </div>
              <span className="status neutral">Live API data</span>
            </header>

            {services.length === 0 ? (
              <div className="data-access-empty">
                <h3>{hasFilters ? "No matching services" : "No services found"}</h3>
                <p>
                  {hasFilters
                    ? "Try another search or select different filters."
                    : "Services published in this project will appear here."}
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table service-directory-table">
                  <thead>
                    <tr>
                      <th scope="col">Service</th>
                      <th scope="col">Capability</th>
                      <th scope="col">Provider ID</th>
                      <th scope="col">Price per call</th>
                      <th scope="col">Protocols</th>
                      <th scope="col">Probe setup</th>
                      <th scope="col">Status</th>
                      <th scope="col">Routing</th>
                    </tr>
                  </thead>
                  <tbody>
                    {services.map((service) => (
                      <tr key={service.id}>
                        <td>
                          <div className="cell-stack">
                            <strong title={service.name}>{service.name}</strong>
                            <span title={service.description ?? undefined}>
                              {service.slug}
                            </span>
                          </div>
                        </td>
                        <td>
                          <code className="service-capability" title={service.capability}>
                            {service.capability}
                          </code>
                        </td>
                        <td>
                          <code className="mono" title={service.provider_id}>
                            {shortId(service.provider_id)}
                          </code>
                        </td>
                        <td className="amount">{displayPrice(service)}</td>
                        <td>
                          <span className="service-protocols">
                            {service.protocols.map((item) => (
                              <span className="status neutral" key={item}>
                                {item.toUpperCase()}
                              </span>
                            ))}
                          </span>
                        </td>
                        <td>
                          <span className="cell-stack service-probe">
                            <strong>{service.health.endpoint}</strong>
                            <span>Every {service.health.interval_seconds}s</span>
                            <span
                              className={`status ${probeTone(service.health)}`}
                              title={
                                service.health.last_check_status_code
                                  ? `HTTP ${service.health.last_check_status_code}`
                                  : undefined
                              }
                            >
                              {probeStatus(service.health)}
                            </span>
                            <span>{probeTime(service.health)}</span>
                            {service.health.consecutive_health_failures ? (
                              <span>
                                {service.health.consecutive_health_failures} consecutive probe failure
                                {service.health.consecutive_health_failures === 1 ? "" : "s"}
                              </span>
                            ) : null}
                          </span>
                        </td>
                        <td>
                          <span className={`status ${statusTone(service.status)}`}>
                            {statusLabel(service.status)}
                          </span>
                        </td>
                        <td className="service-status-cell">
                          <ServiceStatusControl
                            service={service}
                            apiKey={apiKey}
                            connectionId={connectionId}
                          />
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
