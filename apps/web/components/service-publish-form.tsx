"use client";

import { useState, type FormEvent } from "react";
import type {
  ServiceCreateInput,
  ServiceProtocolName,
  ServiceRecord,
} from "@/hooks/use-services";
import { publishService } from "@/hooks/use-services";
import { ApiError } from "@/lib/api-client";

interface ServicePublishFormProps {
  apiKey: string;
  onPublished: (service: ServiceRecord) => void;
}

const PROTOCOLS: ServiceProtocolName[] = ["http", "mcp"];
const CAPABILITY_PATTERN = /^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$/;

function slugFromName(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64)
    .replace(/-+$/g, "");
}

function toAtomicAmount(value: string) {
  const amount = value.trim();
  if (!/^\d+(?:\.\d{1,6})?$/.test(amount)) {
    throw new Error("Enter a USDX amount with up to 6 decimal places.");
  }
  const [whole, fraction = ""] = amount.split(".");
  if (whole.length > 72) throw new Error("The amount is too large to store.");
  const atomic = BigInt(whole) * 1_000_000n + BigInt(fraction.padEnd(6, "0"));
  if (atomic.toString().length > 78) throw new Error("The amount is too large to store.");
  return atomic.toString();
}

function isSafeHealthPath(value: string) {
  return (
    value.startsWith("/") &&
    !value.startsWith("//") &&
    !value.includes("\\") &&
    !/[?#\x00-\x1f\x7f]/.test(value) &&
    !value.split("/").some((segment) => segment === "." || segment === "..")
  );
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "The API key was not accepted. Check it and try again.";
    if (error.status === 403) return "This key needs services:write access to publish services.";
    if (error.status === 404) {
      return "That provider was not found in this project and environment. Copy its ID from Providers and try again.";
    }
    if (error.status === 409) return "That service ID is already in use for this provider and environment.";
    if (error.status === 422) {
      return "Check the provider ID, capability, price, URLs, health settings, and MCP tool schema.";
    }
    return `Service publishing failed (HTTP ${error.status}). Try again shortly.`;
  }
  if (error instanceof Error) return error.message;
  return "The API could not be reached. Check that it is running and try again.";
}

export function ServicePublishForm({ apiKey, onPublished }: ServicePublishFormProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successService, setSuccessService] = useState<ServiceRecord | null>(null);
  const [copyMessage, setCopyMessage] = useState("");
  const [providerId, setProviderId] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [capability, setCapability] = useState("");
  const [protocol, setProtocol] = useState<ServiceProtocolName>("http");
  const [mcpToolName, setMcpToolName] = useState("");
  const [mcpInputSchema, setMcpInputSchema] = useState(
    '{\n  "type": "object",\n  "properties": {}\n}',
  );
  const [price, setPrice] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [healthEndpoint, setHealthEndpoint] = useState("/health");
  const [healthInterval, setHealthInterval] = useState("30");
  const [healthTimeout, setHealthTimeout] = useState("5");
  const [failureThreshold, setFailureThreshold] = useState("3");
  const [version, setVersion] = useState("1.0.0");
  const [description, setDescription] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccessService(null);
    setCopyMessage("");

    try {
      if (!CAPABILITY_PATTERN.test(capability.trim())) {
        throw new Error("Use a lowercase capability such as research.web-search.");
      }
      if (!isSafeHealthPath(healthEndpoint.trim())) {
        throw new Error("Use a health-check path on the service host, such as /health.");
      }
      let mcpSchema: Record<string, unknown> | null = null;
      if (protocol === "mcp") {
        if (!/^[A-Za-z0-9_-]{1,128}$/.test(mcpToolName.trim())) {
          throw new Error("Enter the exact MCP tool name exposed by the provider.");
        }
        let parsedSchema: unknown;
        try {
          parsedSchema = JSON.parse(mcpInputSchema);
        } catch {
          throw new Error("The MCP input schema must be valid JSON.");
        }
        if (
          parsedSchema === null ||
          typeof parsedSchema !== "object" ||
          Array.isArray(parsedSchema) ||
          (parsedSchema as Record<string, unknown>).type !== "object"
        ) {
          throw new Error('The MCP input schema must be a JSON object with "type": "object".');
        }
        mcpSchema = parsedSchema as Record<string, unknown>;
      }
      const input: ServiceCreateInput = {
        name: name.trim(),
        slug: slug.trim(),
        capability: capability.trim(),
        protocols: [protocol],
        mcp_tool_name: protocol === "mcp" ? mcpToolName.trim() : null,
        mcp_input_schema: mcpSchema,
        price_per_call: {
          amount_atomic: toAtomicAmount(price),
          currency: "USDX",
          decimals: 6,
        },
        base_url: baseUrl.trim(),
        endpoint_url: endpointUrl.trim(),
        health: {
          endpoint: healthEndpoint.trim(),
          interval_seconds: Number(healthInterval),
          timeout_seconds: Number(healthTimeout),
          failure_threshold: Number(failureThreshold),
        },
        version: version.trim(),
        description: description.trim() || null,
      };
      const created = await publishService(apiKey, providerId.trim(), input);
      setSuccessService(created);
      onPublished(created);
      setProviderId("");
      setName("");
      setSlug("");
      setSlugEdited(false);
      setCapability("");
      setProtocol("http");
      setMcpToolName("");
      setMcpInputSchema('{\n  "type": "object",\n  "properties": {}\n}');
      setPrice("");
      setBaseUrl("");
      setEndpointUrl("");
      setHealthEndpoint("/health");
      setHealthInterval("30");
      setHealthTimeout("5");
      setFailureThreshold("3");
      setVersion("1.0.0");
      setDescription("");
      setOpen(false);
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  async function copyServiceId() {
    if (!successService) return;
    try {
      await navigator.clipboard.writeText(successService.id);
      setCopyMessage("Service ID copied.");
    } catch {
      setCopyMessage("Copy was unavailable. Select the service ID shown here.");
    }
  }

  return (
    <section className="resource-create-section">
      <button
        className="button primary"
        type="button"
        aria-expanded={open}
        onClick={() => {
          setError("");
          setSuccessService(null);
          setCopyMessage("");
          setOpen((current) => !current);
        }}
      >
        {open ? "Close publishing form" : "Publish a service"}
      </button>

      {successService ? (
        <div className="resource-create-success" role="status">
          <span>
            Published <strong>{successService.name}</strong> at{" "}
            {successService.price_per_call
              ? `${formatPrice(successService.price_per_call)} per call.`
              : "the configured price."}
            {" "}Routing starts after its first health probe passes.
          </span>
          <code className="mono">{successService.id}</code>
          <button className="button ghost" type="button" onClick={() => void copyServiceId()}>
            Copy service ID
          </button>
          {copyMessage ? <span className="card-meta">{copyMessage}</span> : null}
        </div>
      ) : null}

      {open ? (
        <section className="card resource-create-card">
          <header className="card-head">
            <div>
              <h2 className="card-title">Publish a paid service</h2>
              <p className="card-description">
                Register a capability, its per-call USDX price, and the URLs
                the gateway and health checker use. Copy the provider UUID from
                the Providers page first.
              </p>
            </div>
          </header>
          <form className="resource-create-form" onSubmit={submit}>
            <label className="resource-form-field resource-form-wide">
              <span>Provider UUID</span>
              <input
                className="search mono"
                required
                maxLength={36}
                pattern="[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
                autoComplete="off"
                value={providerId}
                onChange={(event) => setProviderId(event.target.value.trim())}
                placeholder="Paste a provider UUID from the Providers page"
              />
            </label>
            <label className="resource-form-field">
              <span>Service name</span>
              <input
                className="search"
                required
                maxLength={128}
                autoComplete="off"
                value={name}
                onChange={(event) => {
                  const nextName = event.target.value;
                  setName(nextName);
                  if (!slugEdited) setSlug(slugFromName(nextName));
                }}
                placeholder="e.g. Market Snapshot"
              />
            </label>
            <label className="resource-form-field">
              <span>Service ID (slug)</span>
              <input
                className="search"
                required
                maxLength={64}
                pattern="[a-z0-9][a-z0-9_-]*"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                value={slug}
                onChange={(event) => {
                  setSlugEdited(true);
                  setSlug(event.target.value);
                }}
                placeholder="market-snapshot"
              />
            </label>
            <label className="resource-form-field">
              <span>Capability</span>
              <input
                className="search mono"
                required
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                value={capability}
                onChange={(event) => setCapability(event.target.value)}
                placeholder="research.market-snapshot"
              />
              <small>Use lowercase dot-separated words, such as research.web-search.</small>
            </label>
            <label className="resource-form-field">
              <span>Price per call (USDX)</span>
              <input
                className="search"
                required
                inputMode="decimal"
                maxLength={80}
                value={price}
                onChange={(event) => setPrice(event.target.value)}
                placeholder="0.05"
              />
              <small>Enter up to 6 decimal places. The amount is stored exactly.</small>
            </label>
            <label className="resource-form-field">
              <span>Invocation protocol</span>
              <select
                className="search"
                value={protocol}
                onChange={(event) => setProtocol(event.target.value as ServiceProtocolName)}
              >
                {PROTOCOLS.map((item) => (
                  <option key={item} value={item}>
                    {item === "http" ? "HTTP JSON" : "MCP Streamable HTTP"}
                  </option>
                ))}
              </select>
              <small>A service version uses one invocation protocol.</small>
            </label>
            {protocol === "mcp" ? (
              <>
                <label className="resource-form-field">
                  <span>Provider MCP tool name</span>
                  <input
                    className="search mono"
                    required
                    maxLength={128}
                    autoComplete="off"
                    value={mcpToolName}
                    onChange={(event) => setMcpToolName(event.target.value)}
                    placeholder="web_search"
                  />
                  <small>The tool name must match the provider's MCP tool listing.</small>
                </label>
                <label className="resource-form-field resource-form-wide">
                  <span>MCP input schema (JSON)</span>
                  <textarea
                    className="search mono"
                    required
                    rows={8}
                    maxLength={32768}
                    spellCheck={false}
                    value={mcpInputSchema}
                    onChange={(event) => setMcpInputSchema(event.target.value)}
                  />
                  <small>
                    Define the published argument contract. Remote JSON Schema references are
                    disabled; references must stay inside this schema.
                  </small>
                </label>
              </>
            ) : null}
            <label className="resource-form-field">
              <span>Service base URL</span>
              <input
                className="search"
                type="url"
                required
                maxLength={2048}
                pattern="https?://.+"
                autoComplete="url"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="https://api.example.com"
              />
              <small>Health checks use this host and the path below.</small>
            </label>
            <label className="resource-form-field">
              <span>Invocation endpoint URL</span>
              <input
                className="search"
                type="url"
                required
                maxLength={2048}
                pattern="https?://.+"
                autoComplete="url"
                value={endpointUrl}
                onChange={(event) => setEndpointUrl(event.target.value)}
                placeholder="https://api.example.com/v1/search"
              />
              <small>The gateway forwards the paid request to this URL.</small>
            </label>
            <label className="resource-form-field">
              <span>Health-check path</span>
              <input
                className="search mono"
                required
                maxLength={512}
                value={healthEndpoint}
                onChange={(event) => setHealthEndpoint(event.target.value)}
                placeholder="/health"
              />
              <small>Use a path on the service host, without a query string.</small>
            </label>
            <label className="resource-form-field">
              <span>Service version</span>
              <input
                className="search"
                required
                maxLength={32}
                value={version}
                onChange={(event) => setVersion(event.target.value)}
                placeholder="1.0.0"
              />
            </label>
            <label className="resource-form-field">
              <span>Health-check interval (seconds)</span>
              <input
                className="search"
                type="number"
                required
                min={5}
                max={3600}
                step={1}
                value={healthInterval}
                onChange={(event) => setHealthInterval(event.target.value)}
              />
            </label>
            <label className="resource-form-field">
              <span>Health-check timeout (seconds)</span>
              <input
                className="search"
                type="number"
                required
                min={1}
                max={30}
                step={1}
                value={healthTimeout}
                onChange={(event) => setHealthTimeout(event.target.value)}
              />
            </label>
            <label className="resource-form-field">
              <span>Failures before unhealthy</span>
              <input
                className="search"
                type="number"
                required
                min={1}
                max={20}
                step={1}
                value={failureThreshold}
                onChange={(event) => setFailureThreshold(event.target.value)}
              />
            </label>
            <label className="resource-form-field resource-form-wide">
              <span>Description <small>(optional)</small></span>
              <textarea
                className="search"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What agents can request from this service"
              />
            </label>
            <p className="resource-form-hint resource-form-wide">
              Use HTTPS for staging and production. At invocation, the gateway
              checks the URL and production host allowlist. Publishing creates
              a service record and version; it does not submit a payment.
            </p>
            {error ? (
              <p className="form-error resource-form-wide" role="alert">
                {error}
              </p>
            ) : null}
            <div className="page-actions resource-form-wide">
              <button className="button primary" type="submit" disabled={busy}>
                {busy ? "Publishing service…" : "Publish service"}
              </button>
            </div>
          </form>
        </section>
      ) : null}
    </section>
  );
}

function formatPrice(price: ServiceRecord["price_per_call"]) {
  if (!price || !/^\d+$/.test(price.amount_atomic)) return "configured price";
  const atomic = BigInt(price.amount_atomic);
  const whole = atomic / 1_000_000n;
  const fraction = (atomic % 1_000_000n)
    .toString()
    .padStart(6, "0")
    .replace(/0+$/, "");
  return `${whole}${fraction ? `.${fraction}` : ""} ${price.currency}`;
}
