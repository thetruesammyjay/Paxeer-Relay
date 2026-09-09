import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/icons";
export const metadata: Metadata = { title: "Overview" };

const transactions = [
  {
    id: "txn_8V4…K2",
    agent: "Research Runner",
    avatar: "RR",
    tone: "orange",
    service: "Atlas Search API",
    route: "402LXP · LayerX",
    amount: "0.024 USDX",
    status: "Settled",
  },
  {
    id: "txn_2M9…Q8",
    agent: "Treasury Scout",
    avatar: "TS",
    tone: "green",
    service: "Paxeer Price Oracle",
    route: "Direct · LayerX",
    amount: "0.008 USDX",
    status: "Verified",
  },
  {
    id: "txn_7H1…F4",
    agent: "Support Triage",
    avatar: "ST",
    tone: "blue",
    service: "Vector Cloud",
    route: "402LXP · LayerX",
    amount: "0.012 USDX",
    status: "Routing",
  },
  {
    id: "txn_4C6…P1",
    agent: "Research Runner",
    avatar: "RR",
    tone: "orange",
    service: "Model Forge",
    route: "Policy v7",
    amount: "0.190 USDX",
    status: "Review",
  },
];

export default function DashboardPage() {
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Agent commerce control plane</div>
          <h1 className="page-title">Every call, under control.</h1>
          <p className="page-subtitle">
            Watch services route, payments clear, and policies hold across your
            autonomous workloads.
          </p>
        </div>
        <div className="page-actions">
          <Link className="button" href="/transactions">
            View activity
          </Link>
          <Link className="button primary" href="/agents">
            <Icon name="plus" width={14} />
            Add agent
          </Link>
        </div>
      </header>
      <section className="grid metrics" aria-label="Workspace metrics">
        <div
          className="card metric"
          style={{ "--metric-color": "var(--safe)" } as React.CSSProperties}
        >
          <div className="metric-label">
            <span>Relay volume</span>
            <Icon name="activity" width={14} />
          </div>
          <div className="metric-value">18,429</div>
          <div className="metric-foot">
            <strong>↑ 12.4%</strong> from last week
          </div>
        </div>
        <div
          className="card metric"
          style={{ "--metric-color": "var(--relay)" } as React.CSSProperties}
        >
          <div className="metric-label">
            <span>Settled today</span>
            <span className="mono">USDX</span>
          </div>
          <div className="metric-value">$284.62</div>
          <div className="metric-foot">Across 1,204 paid calls</div>
        </div>
        <div
          className="card metric"
          style={{ "--metric-color": "var(--info)" } as React.CSSProperties}
        >
          <div className="metric-label">
            <span>Success rate</span>
            <span className="mono">7D</span>
          </div>
          <div className="metric-value">99.82%</div>
          <div className="metric-foot">
            <strong>+0.06%</strong> within target
          </div>
        </div>
        <div
          className="card metric"
          style={{ "--metric-color": "var(--warn)" } as React.CSSProperties}
        >
          <div className="metric-label">
            <span>Needs attention</span>
            <span className="mono">NOW</span>
          </div>
          <div className="metric-value">2</div>
          <div className="metric-foot">Human approvals waiting</div>
        </div>
      </section>
      <section className="grid two" style={{ marginTop: 14 }}>
        <div className="stack">
          <div className="card relay-panel">
            <div className="relay-top">
              <div>
                <div className="relay-kicker">Live relay · req_91B7F2</div>
                <h2 className="relay-title">
                  Research Runner is buying a verified market snapshot.
                </h2>
              </div>
              <div className="relay-live">
                <i className="pulse" /> 247 ms elapsed
              </div>
            </div>
            <div className="relay-trace">
              <div className="trace-step done">
                <span className="trace-dot">✓</span>
                <span className="trace-label">Request received</span>
                <span className="trace-meta">tool.market_snapshot</span>
              </div>
              <div className="trace-step done">
                <span className="trace-dot">✓</span>
                <span className="trace-label">Policy cleared</span>
                <span className="trace-meta">0.024 / 0.50 USDX</span>
              </div>
              <div className="trace-step active">
                <span className="trace-dot">03</span>
                <span className="trace-label">Settling on LayerX</span>
                <span className="trace-meta">provider Atlas · lane 2</span>
              </div>
              <div className="trace-step">
                <span className="trace-dot">04</span>
                <span className="trace-label">Issue receipt</span>
                <span className="trace-meta">signature pending</span>
              </div>
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h2 className="card-title">Recent transactions</h2>
              <Link href="/transactions" className="card-meta">
                OPEN LEDGER →
              </Link>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Transaction</th>
                    <th>Agent</th>
                    <th>Service / route</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((row) => (
                    <tr key={row.id}>
                      <td className="primary-cell mono">{row.id}</td>
                      <td>
                        <div className="agent-cell">
                          <span className={`agent-avatar ${row.tone}`}>
                            {row.avatar}
                          </span>
                          <span className="primary-cell">{row.agent}</span>
                        </div>
                      </td>
                      <td>
                        <span className="cell-stack">
                          <strong>{row.service}</strong>
                          <span>{row.route}</span>
                        </span>
                      </td>
                      <td className="amount">{row.amount}</td>
                      <td>
                        <span className={`status ${row.status.toLowerCase()}`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <aside className="stack">
          <div className="card">
            <div className="card-head">
              <h2 className="card-title">Approval queue</h2>
              <span className="status pending">2 waiting</span>
            </div>
            <div className="approval">
              <div className="approval-top">
                <span className="approval-mark">!</span>
                <div>
                  <h3>Model Forge · 0.190 USDX</h3>
                  <p>
                    Research Runner needs a one-time exception above its
                    per-call limit.
                  </p>
                </div>
              </div>
              <div className="approval-facts">
                <div className="approval-fact">
                  <span>Current limit</span>
                  <strong>0.10 USDX</strong>
                </div>
                <div className="approval-fact">
                  <span>Requested</span>
                  <strong>0.19 USDX</strong>
                </div>
                <div className="approval-fact">
                  <span>Expires in</span>
                  <strong>08:42</strong>
                </div>
              </div>
              <div className="approval-actions">
                <button className="button attention">Review request</button>
                <button className="button ghost">Deny</button>
              </div>
            </div>
            <div style={{ padding: "0 14px 14px" }}>
              <Link
                href="/approvals"
                className="button"
                style={{ width: "100%" }}
              >
                See all approvals
              </Link>
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h2 className="card-title">Spend cadence</h2>
              <span className="card-meta">LAST 12 HOURS</span>
            </div>
            <div className="mini-chart">
              {[
                22, 34, 28, 46, 31, 68, 48, 55, 42, 81, 60, 74, 50, 92, 64, 70,
                58, 84,
              ].map((height, i) => (
                <i
                  key={i}
                  className={`bar ${i > 14 ? "accent" : ""}`}
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
            <div className="chart-legend">
              <span>00:00</span>
              <span>12:00</span>
              <strong style={{ color: "var(--ink)" }}>$284.62</strong>
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h2 className="card-title">What just happened</h2>
              <span className="card-meta">LIVE</span>
            </div>
            {[
              ["check", "Receipt verified", "Atlas Search · txn_8V4…K2", "18s"],
              [
                "policies",
                "Policy blocked overspend",
                "Research Runner · rule_04",
                "2m",
              ],
              [
                "activity",
                "Provider route recovered",
                "Vector Cloud · fallback B",
                "7m",
              ],
            ].map(([icon, title, body, time]) => (
              <div className="activity-row" key={title}>
                <span className="activity-icon">
                  <Icon name={icon as "check"} width={14} />
                </span>
                <span className="activity-copy">
                  <strong>{title}</strong>
                  <span>{body}</span>
                </span>
                <span className="activity-time">{time}</span>
              </div>
            ))}
          </div>
        </aside>
      </section>
    </div>
  );
}
