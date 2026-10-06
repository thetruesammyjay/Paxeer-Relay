"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { dashboardRequiresSso, useApiSession } from "@/lib/api-session";

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
          ? `${session.workspace?.environment ?? "Workspace"} connected`
          : session.status === "checking"
            ? "Checking workspace…"
            : session.status === "selecting"
              ? "Choose a project"
              : "Workspace access"}
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
                {session.workspace ? "Workspace connection" : "Workspace access"}
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
                  Connected to a {session.workspace.environment} project. Data
                  is scoped to this project and your assigned permissions.
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
                {session.workspace.role ? (
                  <div>
                    <dt>Your role</dt>
                    <dd>{session.workspace.role}</dd>
                  </div>
                ) : null}
              </dl>
              <div className="api-session-scopes">
                <strong>Granted API scopes</strong>
                <ul>
                  {session.workspace.scopes.map((scope) => <li key={scope}><code>{scope}</code></li>)}
                </ul>
              </div>
              {session.projects.length > 1 ? (
                <label className="api-session-field">
                  <span>Switch project</span>
                  <select
                    value={session.workspace.project_id}
                    onChange={(event) => void session.selectProject(event.target.value)}
                  >
                    {session.projects.map((project) => (
                      <option key={project.project_id} value={project.project_id}>
                        {project.organisation_name} / {project.project_name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
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
          ) : session.projects.length > 1 ? (
            <div className="api-session-form">
              <p>Select the project you want to open.</p>
              {session.error ? <p className="api-session-error" role="alert">{session.error}</p> : null}
              <div className="api-session-project-list">
                {session.projects.map((project) => (
                  <button
                    className="button secondary"
                    key={project.project_id}
                    type="button"
                    onClick={() => void session.selectProject(project.project_id)}
                  >
                    {project.organisation_name} / {project.project_name}
                    <small>{project.role} · {project.environment}</small>
                  </button>
                ))}
              </div>
            </div>
          ) : dashboardRequiresSso() ? (
            <div className="api-session-form">
              <p>Dashboard access uses your team sign-in and assigned project role.</p>
              {session.error ? <p className="api-session-error" role="alert">{session.error}</p> : null}
              {session.isSignedIn ? (
                <button className="button danger" type="button" onClick={session.disconnect}>
                  Sign out
                </button>
              ) : (
                <Link className="button primary" href="/sign-in">Sign in with your team</Link>
              )}
            </div>
          ) : (
            <form className="api-session-form" onSubmit={(event) => void submit(event)}>
              <p>
                  Enter a development API key. The API confirms its environment
                before any dashboard data is loaded. The key stays in memory
                until you disconnect or reload.
              </p>
              <label className="api-session-field">
                <span>Development API key</span>
                <input
                  type="password"
                  autoComplete="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  required
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Paste a development project key"
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
                {busy ? "Verifying key…" : "Connect development workspace"}
              </button>
            </form>
          )}
        </section>
      ) : null}
    </div>
  );
}
