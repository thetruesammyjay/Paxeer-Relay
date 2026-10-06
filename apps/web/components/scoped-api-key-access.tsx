"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { HugeiconsIcon } from "@hugeicons/react";
import { ShieldCheckIcon } from "@hugeicons/core-free-icons";
import { dashboardRequiresSso, useApiSession } from "@/lib/api-session";
import { OIDC_SESSION_TOKEN } from "@/lib/api-client";

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
  title = "Connect to your workspace",
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
  const ssoRequired = dashboardRequiresSso();

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
  const isTeamSession = session.apiKey === OIDC_SESSION_TOKEN || apiKey === OIDC_SESSION_TOKEN;
  const missingScopes = session.workspace
    ? requiredScopes.filter((requiredScope) => !session.workspace?.scopes.includes(requiredScope))
    : [];

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
            Your project access is checked for{" "}
            {requiredScopes.map((requiredScope, index) => (
              <span key={requiredScope}>
                {index > 0 ? " and " : null}
                <code>{requiredScope}</code>
              </span>
            ))}. Production dashboards use your team sign-in. Local development
            can use a development API key.
          </p>
        </div>
      </div>

      {hasConnection ? (
        <div className="scoped-key-connected">
          <span
            className={`status ${visibleError || missingScopes.length ? "denied" : connected ? "active" : loading ? "pending" : "active"}`}
          >
            {visibleError || missingScopes.length
              ? "Access needs attention"
              : loading
                ? "Loading live data"
                : isTeamSession
                  ? "Team sign-in connected"
                  : "Development key connected"}
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
          {visibleError || missingScopes.length ? (
            <span className="data-access-error-inline" role="alert">
              {visibleError || `Your project role does not include ${missingScopes.join(" and ")}.`}
            </span>
          ) : null}
          {isTeamSession && session.workspace ? (
            <span className="data-access-error-inline">
              Connected to {session.workspace.project_id} as {session.workspace.role}.
            </span>
          ) : null}
        </div>
      ) : ssoRequired ? (
        <div className="scoped-key-connected">
          <span className="status pending">
            {session.status === "checking"
              ? "Checking team access"
              : session.status === "selecting"
                ? "Choose a project"
                : "Team sign-in required"}
          </span>
          {session.error ? (
            <span className="data-access-error-inline" role="alert">{session.error}</span>
          ) : null}
          {session.status === "selecting" ? (
            <span className="data-access-error-inline">Choose a project from the workspace control in the header.</span>
          ) : null}
          {!session.isSignedIn ? <Link className="button primary" href="/sign-in">Sign in with your team</Link> : null}
        </div>
      ) : (
        <form
          className="scoped-key-form"
          onSubmit={(event) => void submit(event)}
        >
          <label className="scoped-key-field">
            <span>Development API key</span>
            <input
              type="password"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder={`Paste a development key with ${requiredScopes.join(" and ")} access`}
              value={draftKey}
              onChange={(event) => setDraftKey(event.target.value)}
              aria-label="Development API key"
            />
          </label>
          <button
            className="button primary"
            type="submit"
            disabled={!draftKey.trim() || loading || connecting}
          >
            {connecting ? "Verifying development key…" : actionLabel}
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
