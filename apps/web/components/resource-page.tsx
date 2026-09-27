"use client";

import { useMemo, useState } from "react";
import { Icon, type IconName } from "./icons";

export type ResourceKind =
  | "transactions"
  | "approvals"
  | "agents"
  | "policies"
  | "providers"
  | "services"
  | "receipts"
  | "analytics"
  | "settings";
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
  transactions: {
    eyebrow: "Execution ledger",
    title: "Transactions",
    description: "Every agent call from request through payment and delivery.",
    action: "Export ledger",
    icon: "transactions",
    columns: ["Transaction", "Agent", "Service", "Amount", "Latency", "Status"],
    rows: [
      [
        "txn_8V4…K2",
        "Research Runner",
        "Atlas Search API",
        "0.024 USDX",
        "247 ms",
        "Settled",
      ],
      [
        "txn_2M9…Q8",
        "Treasury Scout",
        "Paxeer Price Oracle",
        "0.008 USDX",
        "91 ms",
        "Verified",
      ],
      [
        "txn_7H1…F4",
        "Support Triage",
        "Vector Cloud",
        "0.012 USDX",
        "312 ms",
        "Routing",
      ],
      [
        "txn_4C6…P1",
        "Research Runner",
        "Model Forge",
        "0.190 USDX",
        "—",
        "Review",
      ],
      [
        "txn_1A3…D7",
        "Treasury Scout",
        "ChainScope RPC",
        "0.006 USDX",
        "118 ms",
        "Settled",
      ],
    ],
  },
  approvals: {
    eyebrow: "Human authority",
    title: "Approvals",
    description:
      "Decide on requests that exceed an agent’s standing permissions.",
    action: "Approval settings",
    icon: "approvals",
    columns: ["Request", "Agent", "Reason", "Amount", "Expires", "Status"],
    rows: [
      [
        "apr_01J…N8",
        "Research Runner",
        "Above per-call cap",
        "0.190 USDX",
        "08:42",
        "Pending",
      ],
      [
        "apr_01J…C4",
        "Treasury Scout",
        "New provider",
        "1.200 USDX",
        "21:06",
        "Pending",
      ],
      [
        "apr_01J…V2",
        "Support Triage",
        "Scope expansion",
        "0.045 USDX",
        "Closed",
        "Denied",
      ],
    ],
  },
  agents: {
    eyebrow: "Autonomous operators",
    title: "Agents",
    description:
      "Give each agent a wallet, a policy, and only the authority it needs.",
    action: "Add agent",
    icon: "agents",
    columns: ["Agent", "Wallet", "Policy", "Spend today", "Calls", "Status"],
    rows: [
      [
        "Research Runner",
        "0x7A3…91F",
        "Research standard",
        "$183.42",
        "8,204",
        "Active",
      ],
      [
        "Treasury Scout",
        "0x2B8…E47",
        "Treasury strict",
        "$74.10",
        "1,986",
        "Active",
      ],
      [
        "Support Triage",
        "0x9D1…2C0",
        "Support tools",
        "$27.10",
        "3,112",
        "Active",
      ],
      ["Release Bot", "0x4F2…A19", "Deploy restricted", "$0.00", "0", "Paused"],
    ],
  },
  policies: {
    eyebrow: "Deterministic controls",
    title: "Policies",
    description:
      "Encode budgets, allowlists, and approval rules before an agent spends.",
    action: "Create policy",
    icon: "policies",
    columns: [
      "Policy",
      "Version",
      "Assigned",
      "Daily cap",
      "Approval above",
      "Status",
    ],
    rows: [
      ["Research standard", "v7", "1 agent", "250 USDX", "0.10 USDX", "Active"],
      ["Treasury strict", "v4", "1 agent", "100 USDX", "1.00 USDX", "Active"],
      ["Support tools", "v2", "1 agent", "50 USDX", "0.05 USDX", "Active"],
      ["Deploy restricted", "v9", "1 agent", "20 USDX", "Any spend", "Paused"],
    ],
  },
  providers: {
    eyebrow: "Routing network",
    title: "Providers",
    description: "Monitor the endpoints that fulfill paid agent requests.",
    action: "Register provider",
    icon: "providers",
    columns: [
      "Provider",
      "Services",
      "Reliability",
      "Median latency",
      "30d volume",
      "Status",
    ],
    rows: [
      ["Atlas Labs", "12", "99.99%", "183 ms", "$18.4k", "Active"],
      ["Paxeer Oracle", "4", "99.97%", "76 ms", "$9.8k", "Active"],
      ["Vector Cloud", "9", "99.82%", "291 ms", "$6.2k", "Active"],
      ["Model Forge", "18", "99.91%", "840 ms", "$24.1k", "Active"],
    ],
  },
  services: {
    eyebrow: "Paid capabilities",
    title: "Services",
    description:
      "Discover routable tools with explicit prices, evidence, and health.",
    action: "Publish service",
    icon: "services",
    columns: [
      "Service",
      "Provider",
      "Capability",
      "Price",
      "p95 latency",
      "Status",
    ],
    rows: [
      [
        "Market snapshot",
        "Atlas Labs",
        "data.market",
        "0.024 USDX",
        "310 ms",
        "Active",
      ],
      [
        "PAX / USDX price",
        "Paxeer Oracle",
        "oracle.price",
        "0.008 USDX",
        "94 ms",
        "Active",
      ],
      [
        "Vector lookup",
        "Vector Cloud",
        "memory.search",
        "0.012 USDX",
        "420 ms",
        "Active",
      ],
      [
        "Reasoning large",
        "Model Forge",
        "model.infer",
        "0.190 USDX",
        "1.4 s",
        "Active",
      ],
    ],
  },
  receipts: {
    eyebrow: "Verifiable evidence",
    title: "Receipts",
    description:
      "Prove what was requested, paid, delivered, and observed by the relay.",
    action: "Verify receipt",
    icon: "receipts",
    columns: [
      "Receipt",
      "Transaction",
      "Provider",
      "Observed at",
      "Anchor",
      "Status",
    ],
    rows: [
      [
        "rcp_01J…4M",
        "txn_8V4…K2",
        "Atlas Labs",
        "09:42:18",
        "LayerX batch 882",
        "Verified",
      ],
      [
        "rcp_01J…1Q",
        "txn_2M9…Q8",
        "Paxeer Oracle",
        "09:41:54",
        "LayerX batch 882",
        "Verified",
      ],
      [
        "rcp_01J…7K",
        "txn_1A3…D7",
        "ChainScope",
        "09:36:07",
        "LayerX batch 881",
        "Verified",
      ],
    ],
  },
  analytics: {
    eyebrow: "Operational intelligence",
    title: "Analytics",
    description:
      "Understand cost, quality, and policy outcomes without losing the underlying evidence.",
    action: "Download report",
    icon: "analytics",
    columns: ["Provider", "Calls", "Spend", "Success", "p95", "Change"],
    rows: [
      ["Atlas Labs", "8,240", "$183.42", "99.99%", "310 ms", "+12.4%"],
      ["Paxeer Oracle", "4,102", "$32.81", "99.97%", "94 ms", "+8.1%"],
      ["Vector Cloud", "3,048", "$36.58", "99.82%", "420 ms", "−2.6%"],
      ["Model Forge", "1,486", "$282.34", "99.91%", "1.4 s", "+21.0%"],
    ],
  },
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
  const isAnalytics = kind === "analytics";
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
      {isAnalytics ? (
        <div className="grid metrics" style={{ marginBottom: 14 }}>
          {[
            ["Total spend", "$537.15", "+11.2%"],
            ["Paid calls", "16,876", "+8.4%"],
            ["Policy blocks", "142", "−4.1%"],
            ["Median cost", "0.018 USDX", "−1.8%"],
          ].map(([label, value, delta], i) => (
            <div
              className="card metric"
              key={label}
              style={
                {
                  "--metric-color":
                    i === 0 ? "var(--relay)" : "var(--line-strong)",
                } as React.CSSProperties
              }
            >
              <div className="metric-label">
                {label}
                <span className="mono">30D</span>
              </div>
              <div className="metric-value">{value}</div>
              <div className="metric-foot">
                <strong>{delta}</strong> over prior period
              </div>
            </div>
          ))}
        </div>
      ) : null}
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
          <h2 className="card-title">
            {kind === "approvals"
              ? "Requests requiring a decision"
              : `All ${config.title.toLowerCase()}`}
          </h2>
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
                rows.map((row, index) => (
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
                        ) : cellIndex === 1 &&
                          ["agents", "transactions", "approvals"].includes(
                            kind,
                          ) ? (
                          <div className="agent-cell">
                            <span
                              className={`agent-avatar ${index % 3 === 0 ? "orange" : index % 3 === 1 ? "green" : "blue"}`}
                            >
                              {cell
                                .split(" ")
                                .map((part) => part[0])
                                .join("")
                                .slice(0, 2)}
                            </span>
                            <span className="primary-cell">{cell}</span>
                          </div>
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
