"use client";

import { useMemo, useState } from "react";
import { Icon, type IconName } from "./icons";

export type ResourceKind = "settings";
type Config = {
  eyebrow: string;
  title: string;
  description: string;
  action: string;
  icon: IconName;
  columns: string[];
  rows: string[][];
};
const CONFIG: Record<ResourceKind, Config> = {
  settings: {
    eyebrow: "Workspace controls",
    title: "Settings",
    description:
      "Manage the workspace, network defaults, members, and security posture.",
    action: "Save changes",
    icon: "settings",
    columns: [
      "Setting",
      "Current value",
      "Scope",
      "Last changed",
      "Owner",
      "Status",
    ],
    rows: [
      [
        "Default network",
        "Paxeer mainnet",
        "Workspace",
        "Sep 02",
        "Sammy",
        "Active",
      ],
      ["Settlement lane", "LayerX", "Workspace", "Sep 02", "Sammy", "Active"],
      [
        "Receipt retention",
        "365 days",
        "Workspace",
        "Aug 29",
        "Mira",
        "Active",
      ],
      [
        "Production approvals",
        "Required",
        "All agents",
        "Aug 28",
        "Sammy",
        "Active",
      ],
    ],
  },
};

const statusTone = (value: string) => {
  const v = value.toLowerCase();
  if (["active", "settled", "verified"].includes(v)) return v;
  if (["pending", "review"].includes(v)) return "pending";
  if (["denied", "suspended"].includes(v)) return "denied";
  if (v === "routing") return "routing";
  if (v === "paused") return "paused";
  return "neutral";
};

export function ResourcePage({ kind }: { kind: ResourceKind }) {
  const config = CONFIG[kind];
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const rows = useMemo(
    () =>
      config.rows.filter((row) =>
        row.some((cell) => cell.toLowerCase().includes(normalizedQuery)),
      ),
    [config.rows, normalizedQuery],
  );
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">{config.eyebrow}</div>
          <h1 className="page-title">{config.title}</h1>
          <p className="page-subtitle">{config.description}</p>
        </div>
        <div className="page-actions">
          <button className="button" type="button" disabled>
            Documentation
          </button>
          <button className="button primary" type="button" disabled>
            <Icon name={kind === "settings" ? "check" : "plus"} width={14} />
            {config.action}
          </button>
        </div>
      </header>
      <div className="preview-note" role="note">
        <span className="preview-note-mark" aria-hidden="true">
          i
        </span>
        <p>
          <strong>Sample data.</strong> These records are examples. Actions on
          this page are not connected to the API.
        </p>
      </div>
      <div className="toolbar">
        <input
          className="search"
          type="search"
          aria-label={`Search ${config.title}`}
          placeholder={`Search ${config.title.toLowerCase()}…`}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="toolbar-spacer" />
        <span className="card-meta" aria-live="polite">
          {rows.length} sample {rows.length === 1 ? "row" : "rows"}
        </span>
      </div>
      <section className="card">
        <div className="card-head">
          <h2 className="card-title">All {config.title.toLowerCase()}</h2>
          <span className="status neutral">Sample data</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {config.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td className="empty-row" colSpan={config.columns.length}>
                    No sample records match this search. Clear the search to
                    see every row.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row[0]}>
                    {row.map((cell, cellIndex) => (
                      <td
                        key={cellIndex}
                        className={
                          cellIndex === 0
                            ? "primary-cell mono"
                            : cell.includes("USDX") || cell.startsWith("$")
                              ? "amount"
                              : ""
                        }
                      >
                        {cellIndex === row.length - 1 ? (
                          <span className={`status ${statusTone(cell)}`}>
                            {cell}
                          </span>
                        ) : (
                          cell
                        )}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
      <div className="detail-grid" style={{ marginTop: 14 }}>
        <div className="card detail-card">
          <div className="eyebrow">Network</div>
          <strong>Chain 125</strong>
          <p>Settling on Paxeer mainnet through the LayerX agent lane.</p>
        </div>
        <div className="card detail-card">
          <div className="eyebrow">Protection</div>
          <strong>Fail closed</strong>
          <p>
            Uncertain payment, policy, or signature state never reaches a
            provider.
          </p>
        </div>
        <div className="card detail-card">
          <div className="eyebrow">Evidence</div>
          <strong>100% receipted</strong>
          <p>
            Every completed paid call leaves a canonical, signed execution
            record.
          </p>
        </div>
      </div>
    </div>
  );
}
