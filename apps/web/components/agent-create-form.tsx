"use client";

import { useState, type FormEvent } from "react";
import type { Agent, AgentCreateInput } from "@/hooks/use-agents";
import { createAgent } from "@/hooks/use-agents";
import { ApiError } from "@/lib/api-client";

interface AgentCreateFormProps {
  apiKey: string;
  onCreated: (agent: Agent) => void;
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
    if (error.status === 401) return "The API key was not accepted. Check it and try again.";
    if (error.status === 403) return "This key needs agents:write access to register agents.";
    if (error.status === 409) return "That agent ID is already in use in this project and environment.";
    if (error.status === 422) return "Check the agent name, ID, and wallet address, then try again.";
    return `Agent registration failed (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check that it is running and try again.";
}

export function AgentCreateForm({ apiKey, onCreated }: AgentCreateFormProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [successAgent, setSuccessAgent] = useState<Agent | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [walletAddress, setWalletAddress] = useState("");
  const [description, setDescription] = useState("");
  const [copyMessage, setCopyMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccessAgent(null);
    const input: AgentCreateInput = {
      name: name.trim(),
      slug: slug.trim(),
      wallet_address: walletAddress.trim() || null,
      description: description.trim() || null,
    };

    try {
      const created = await createAgent(apiKey, input);
      setName("");
      setSlug("");
      setSlugEdited(false);
      setWalletAddress("");
      setDescription("");
      setOpen(false);
      setSuccessAgent(created);
      onCreated(created);
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  async function copyAgentId() {
    if (!successAgent) return;
    try {
      await navigator.clipboard.writeText(successAgent.id);
      setCopyMessage("Agent ID copied.");
    } catch {
      setCopyMessage("Copy was unavailable. Select the Agent ID shown here.");
    }
  }

  return (
    <section className="agent-create-section">
      <button
        className="button primary"
        type="button"
        aria-expanded={open}
        onClick={() => {
          setError("");
          setSuccessAgent(null);
          setCopyMessage("");
          setOpen((current) => !current);
        }}
      >
        {open ? "Close registration form" : "Register agent"}
      </button>

      {successAgent ? (
        <div className="agent-create-success" role="status">
          <span>
            Registered <strong>{successAgent.name}</strong> in the {successAgent.environment} environment.
          </span>
          <code className="mono">{successAgent.id}</code>
          <button className="button ghost" type="button" onClick={() => void copyAgentId()}>
            Copy agent ID
          </button>
          {copyMessage ? <span className="card-meta">{copyMessage}</span> : null}
        </div>
      ) : null}

      {open ? (
        <section className="card agent-create-card">
          <header className="card-head">
            <div>
              <h2 className="card-title">Register an agent</h2>
              <p className="card-description">
                Add an agent to this project and environment with a key that has agents:write access. You can connect a spending policy after registration.
              </p>
            </div>
          </header>
          <form className="agent-create-form" onSubmit={submit}>
            <label className="agent-form-field">
              <span>Agent name</span>
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
                placeholder="e.g. Research Runner"
              />
            </label>
            <label className="agent-form-field">
              <span>Agent ID (slug)</span>
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
                placeholder="research-runner"
              />
              <small>Use lowercase letters, numbers, hyphens, or underscores.</small>
            </label>
            <label className="agent-form-field">
              <span>Wallet address <small>(optional)</small></span>
              <input
                className="search mono"
                inputMode="text"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                pattern="0x[a-fA-F0-9]{40}"
                value={walletAddress}
                onChange={(event) => setWalletAddress(event.target.value)}
                placeholder="0x…"
              />
              <small>Links an existing address to this record. It does not connect a wallet or enable payments.</small>
            </label>
            <label className="agent-form-field agent-form-wide">
              <span>Description <small>(optional)</small></span>
              <textarea
                className="search"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this agent is responsible for"
              />
            </label>
            {error ? <p className="form-error agent-form-wide" role="alert">{error}</p> : null}
            <div className="page-actions agent-form-wide">
              <button className="button primary" type="submit" disabled={busy}>
                {busy ? "Registering agent…" : "Register agent"}
              </button>
            </div>
          </form>
        </section>
      ) : null}
    </section>
  );
}
