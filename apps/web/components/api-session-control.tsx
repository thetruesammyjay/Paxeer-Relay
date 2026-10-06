"use client";

import { useState, type FormEvent } from "react";
import { useApiSession } from "@/lib/api-session";

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

export function ApiSessionControl() {
  const session = useApiSession();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const connected = await session.connect(draft);
    setBusy(false);
    if (connected) {
      setDraft("");
      setOpen(false);
    }
  }

  return (
    <div className="api-session-control">
      <button
        className={`network-pill ${session.status === "connected" ? "network-production" : "network-disconnected"}`}
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((value) => !value)}
      >
        <i aria-hidden="true" />
        {session.status === "connected"
          ? "Production API connected"
          : session.status === "checking"
            ? "Checking production key…"
            : "Connect production API"}
      </button>

      {open ? (
        <section
          className="api-session-popover"
          role="dialog"
          aria-labelledby="api-session-title"
        >
          <header>
            <div>
              <p className="eyebrow">Live workspace data</p>
              <h2 id="api-session-title">
                {session.workspace ? "Production connection" : "Connect production API"}
              </h2>
            </div>
            <button
              className="api-session-close"
              type="button"
              aria-label="Close connection panel"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </header>

          {session.workspace ? (
            <div className="api-session-details">
              <p>
                Connected to a production project. Data stays scoped to this
                key&apos;s project and permissions.
              </p>
              <dl>
                <div>
                  <dt>Project</dt>
                  <dd>{shortId(session.workspace.project_id)}</dd>
                </div>
                <div>
                  <dt>Environment</dt>
                  <dd>{session.workspace.environment}</dd>
                </div>
                <div>
                  <dt>Access grants</dt>
                  <dd>{session.workspace.scopes.length}</dd>
                </div>
              </dl>
              <div className="api-session-scopes">
                <strong>Granted API scopes</strong>
                <ul>
                  {session.workspace.scopes.map((scope) => <li key={scope}><code>{scope}</code></li>)}
                </ul>
              </div>
              <button
                className="button danger"
                type="button"
                onClick={() => {
                  session.disconnect();
                  setOpen(false);
                }}
              >
                Disconnect and clear data
              </button>
            </div>
          ) : (
            <form className="api-session-form" onSubmit={(event) => void submit(event)}>
              <p>
                Enter a production API key. The API confirms its environment
                before any dashboard data is loaded. The key stays in memory
                until you disconnect or reload.
              </p>
              <label className="api-session-field">
                <span>Production API key</span>
                <input
                  type="password"
                  autoComplete="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  required
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Paste a production project key"
                />
              </label>
              {session.error ? (
                <p className="api-session-error" role="alert">
                  {session.error}
                </p>
              ) : null}
              <button
                className="button primary"
                type="submit"
                disabled={busy || !draft.trim()}
              >
                {busy ? "Verifying key…" : "Connect production workspace"}
              </button>
            </form>
          )}
        </section>
      ) : null}
    </div>
  );
}
