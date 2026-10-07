"use client";

import { useState, type FormEvent } from "react";
import type { ProviderCreateInput, ProviderRecord } from "@/hooks/use-providers";
import { createProvider } from "@/hooks/use-providers";
import { ApiError } from "@/lib/api-client";

interface ProviderCreateFormProps {
  apiKey: string;
  onCreated: (provider: ProviderRecord) => void;
}

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

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your workspace session is no longer valid. Sign in again or reconnect the development key.";
    if (error.status === 403) return "Your current project access needs providers:write permission to register providers.";
    if (error.code === "invalid_request") {
      return "Add the payment destination required by the selected environment, then try again.";
    }
    if (error.status === 409) return "That provider ID is already in use in this project and environment.";
    if (error.status === 422) return "Check the provider name, ID, website, and payment address, then try again.";
    return `Provider registration failed (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

export function ProviderCreateForm({ apiKey, onCreated }: ProviderCreateFormProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successProvider, setSuccessProvider] = useState<ProviderRecord | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [walletAddress, setWalletAddress] = useState("");
  const [layerxAccountId, setLayerxAccountId] = useState("");
  const [solanaDevnetAddress, setSolanaDevnetAddress] = useState("");
  const [description, setDescription] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [copyMessage, setCopyMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccessProvider(null);
    const input: ProviderCreateInput = {
      name: name.trim(),
      slug: slug.trim(),
      wallet_address: walletAddress.trim() || null,
      layerx_account_id: layerxAccountId.trim().toLowerCase() || null,
      solana_devnet_address: solanaDevnetAddress.trim() || null,
      description: description.trim() || null,
      website_url: websiteUrl.trim() || null,
    };

    try {
      const created = await createProvider(apiKey, input);
      setName("");
      setSlug("");
      setSlugEdited(false);
      setWalletAddress("");
      setLayerxAccountId("");
      setSolanaDevnetAddress("");
      setDescription("");
      setWebsiteUrl("");
      setOpen(false);
      setSuccessProvider(created);
      onCreated(created);
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  async function copyProviderId() {
    if (!successProvider) return;
    try {
      await navigator.clipboard.writeText(successProvider.id);
      setCopyMessage("Provider ID copied.");
    } catch {
      setCopyMessage("Copy was unavailable. Select the provider ID shown here.");
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
          setSuccessProvider(null);
          setCopyMessage("");
          setOpen((current) => !current);
        }}
      >
        {open ? "Close registration form" : "Register provider"}
      </button>

      {successProvider ? (
        <div className="resource-create-success" role="status">
          <span>
            Registered <strong>{successProvider.name}</strong> in the {successProvider.environment} environment.
          </span>
          <code className="mono">{successProvider.id}</code>
          <button className="button ghost" type="button" onClick={() => void copyProviderId()}>
            Copy provider ID
          </button>
          {copyMessage ? <span className="card-meta">{copyMessage}</span> : null}
        </div>
      ) : null}

      {open ? (
        <section className="card resource-create-card">
          <header className="card-head">
            <div>
              <h2 className="card-title">Register a provider</h2>
              <p className="card-description">
                Add a provider destination for each payment rail you plan to use. Solana Devnet is for testing only.
              </p>
            </div>
          </header>
          <form className="resource-create-form" onSubmit={submit}>
            <label className="resource-form-field">
              <span>Provider name</span>
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
                placeholder="e.g. Acme Research API"
              />
            </label>
            <label className="resource-form-field">
              <span>Provider ID (slug)</span>
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
                placeholder="acme-research-api"
              />
              <small>Use lowercase letters, numbers, hyphens, or underscores.</small>
            </label>
            <label className="resource-form-field resource-form-wide">
              <span>Payment wallet address <small>(required in production)</small></span>
              <input
                className="search mono"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                pattern="0x[a-fA-F0-9]{40}"
                value={walletAddress}
                onChange={(event) => setWalletAddress(event.target.value)}
                placeholder="0x…"
              />
              <small>This records a destination address; it does not connect a wallet or prove ownership.</small>
            </label>
            <label className="resource-form-field resource-form-wide">
              <span>LayerX account ID <small>(required for live payments)</small></span>
              <input
                className="search mono"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                pattern="[a-fA-F0-9]{64}"
                maxLength={64}
                value={layerxAccountId}
                onChange={(event) => setLayerxAccountId(event.target.value)}
                placeholder="64-character LayerX account ID"
              />
              <small>LayerX payment destination, as 32-byte lowercase hexadecimal.</small>
            </label>
            <label className="resource-form-field resource-form-wide">
              <span>Solana Devnet address <small>(optional; test rail only)</small></span>
              <input
                className="search mono"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                minLength={32}
                maxLength={44}
                pattern="[1-9A-HJ-NP-Za-km-z]{32,44}"
                value={solanaDevnetAddress}
                onChange={(event) => setSolanaDevnetAddress(event.target.value)}
                placeholder="Base58 Solana public key"
              />
              <small>Receives test USDC on Solana Devnet. Do not use a mainnet address as a production payment destination.</small>
            </label>
            <label className="resource-form-field resource-form-wide">
              <span>Website <small>(optional)</small></span>
              <input
                className="search"
                type="url"
                maxLength={2048}
                pattern="https?://.+"
                autoComplete="url"
                value={websiteUrl}
                onChange={(event) => setWebsiteUrl(event.target.value)}
                placeholder="https://example.com"
              />
              <small>Enter a public HTTP or HTTPS address.</small>
            </label>
            <label className="resource-form-field resource-form-wide">
              <span>Description <small>(optional)</small></span>
              <textarea
                className="search"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this provider offers"
              />
            </label>
            {error ? <p className="form-error resource-form-wide" role="alert">{error}</p> : null}
            <div className="page-actions resource-form-wide">
              <button className="button primary" type="submit" disabled={busy}>
                {busy ? "Registering provider…" : "Register provider"}
              </button>
            </div>
          </form>
        </section>
      ) : null}
    </section>
  );
}
