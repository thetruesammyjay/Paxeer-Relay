"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { HugeiconsIcon } from "@hugeicons/react";
import { ShieldCheckIcon } from "@hugeicons/core-free-icons";
import { useApiSession } from "@/lib/api-session";

interface ScopedApiKeyAccessProps {
  scope: string;
  additionalScopes?: string[];
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
  additionalScopes = [],
  title = "Connect to your production workspace",
  actionLabel,
  apiKey,
  connected,
  loading,
  error,
  onConnect,
  onDisconnect,
}: ScopedApiKeyAccessProps) {
  const session = useApiSession();
  const [draftKey, setDraftKey] = useState("");
  const [connecting, setConnecting] = useState(false);
  const lastSyncedKey = useRef("");
  const lastDisconnectedKey = useRef("");
  const requiredScopes = [scope, ...additionalScopes];

  useEffect(() => {
    if (!session.apiKey) {
      lastSyncedKey.current = "";
      if (apiKey && lastDisconnectedKey.current !== apiKey) {
        lastDisconnectedKey.current = apiKey;
        onDisconnect();
      }
      if (!apiKey) lastDisconnectedKey.current = "";
      return;
    }
    lastDisconnectedKey.current = "";
    if (session.apiKey !== apiKey && lastSyncedKey.current !== session.apiKey) {
      lastSyncedKey.current = session.apiKey;
      onConnect(session.apiKey);
    }
  }, [apiKey, onConnect, onDisconnect, session.apiKey]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = draftKey.trim();
    if (!key) return;
    setConnecting(true);
    if (await session.connect(key)) {
      setDraftKey("");
      onConnect(key);
    }
    setConnecting(false);
  }

  const hasConnection = Boolean(session.apiKey || apiKey);
  const visibleError = session.error || error;

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
            Connect a production key with{" "}
            {requiredScopes.map((requiredScope, index) => (
              <span key={requiredScope}>
                {index > 0 ? " and " : null}
                <code>{requiredScope}</code>
              </span>
            ))}. The API confirms its environment. The key stays in memory
            across dashboard pages and clears when you disconnect or reload.
          </p>
        </div>
      </div>

      {hasConnection ? (
        <div className="scoped-key-connected">
          <span
            className={`status ${visibleError ? "denied" : connected ? "active" : loading ? "pending" : "active"}`}
          >
            {visibleError
              ? "Key needs attention"
              : loading
                ? "Loading live data"
                : "Production key connected"}
          </span>
          <button
            className="button ghost"
            type="button"
            onClick={() => {
              session.disconnect();
              onDisconnect();
            }}
            disabled={loading || connecting}
          >
            Disconnect
          </button>
          {visibleError ? (
            <span className="data-access-error-inline" role="alert">
              {visibleError}
            </span>
          ) : null}
        </div>
      ) : (
        <form
          className="scoped-key-form"
          onSubmit={(event) => void submit(event)}
        >
          <label className="scoped-key-field">
            <span>Production API key</span>
            <input
              type="password"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder={`Paste a production key with ${requiredScopes.join(" and ")} access`}
              value={draftKey}
              onChange={(event) => setDraftKey(event.target.value)}
              aria-label="Production API key"
            />
          </label>
          <button
            className="button primary"
            type="submit"
            disabled={!draftKey.trim() || loading || connecting}
          >
            {connecting ? "Verifying production key…" : actionLabel}
          </button>
          {session.error ? (
            <p className="api-session-error" role="alert">
              {session.error}
            </p>
          ) : null}
        </form>
      )}
    </section>
  );
}
