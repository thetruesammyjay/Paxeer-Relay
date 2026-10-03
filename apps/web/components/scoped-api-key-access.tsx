"use client";

import { useState, type FormEvent } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { ShieldCheckIcon } from "@hugeicons/core-free-icons";

interface ScopedApiKeyAccessProps {
  scope: string;
  title?: string;
  actionLabel: string;
  apiKey: string;
  connected: boolean;
  loading: boolean;
  error: string;
  onConnect: (key: string) => void;
  onDisconnect: () => void;
}

export function ScopedApiKeyAccess({
  scope,
  title = "Connect to your workspace",
  actionLabel,
  apiKey,
  connected,
  loading,
  error,
  onConnect,
  onDisconnect,
}: ScopedApiKeyAccessProps) {
  const [draftKey, setDraftKey] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = draftKey.trim();
    if (!key) return;
    setDraftKey("");
    onConnect(key);
  }

  return (
    <section className="scoped-key-access" aria-labelledby="scoped-key-title">
      <div className="scoped-key-access-copy">
        <div className="scoped-key-access-mark" aria-hidden="true">
          <HugeiconsIcon
            icon={ShieldCheckIcon}
            size={22}
            color="currentColor"
            strokeWidth={1.7}
          />
        </div>
        <div>
          <h2 id="scoped-key-title">{title}</h2>
          <p>
            Enter an API key with <code>{scope}</code> access. The key stays in
            this page&apos;s memory and is cleared when you leave or change it.
          </p>
        </div>
      </div>

      {apiKey ? (
        <div className="scoped-key-connected">
          <span
            className={`status ${connected ? "active" : error ? "denied" : "pending"}`}
          >
            {connected
              ? "Connected for this session"
              : error
                ? "Key needs attention"
                : loading
                  ? "Checking API key"
                  : "Waiting for API"}
          </span>
          <button className="button ghost" type="button" onClick={onDisconnect}>
            Change key
          </button>
        </div>
      ) : (
        <form className="scoped-key-form" onSubmit={submit}>
          <label className="scoped-key-field">
            <span>Workspace API key</span>
            <input
              type="password"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder={`Paste a key with ${scope} access`}
              value={draftKey}
              onChange={(event) => setDraftKey(event.target.value)}
              aria-label="Workspace API key"
            />
          </label>
          <button
            className="button primary"
            type="submit"
            disabled={!draftKey.trim() || loading}
          >
            {actionLabel}
          </button>
        </form>
      )}
    </section>
  );
}
