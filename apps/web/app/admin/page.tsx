import type { Metadata } from "next";
import Link from "next/link";
import type { Route } from "next";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  Activity01Icon,
  Building01Icon,
  CheckmarkCircle01Icon,
  Invoice01Icon,
  Notification03Icon,
  Settings01Icon,
  UserIcon,
  UserGroupIcon,
} from "@hugeicons/core-free-icons";

export const metadata: Metadata = { title: "Admin dashboard" };

const metrics = [
  {
    label: "Active workspaces",
    value: "08",
    detail: "Across the demo network",
    icon: Building01Icon,
    tone: "safe",
  },
  {
    label: "Creator accounts",
    value: "23",
    detail: "3 waiting for review",
    icon: UserGroupIcon,
    tone: "relay",
  },
  {
    label: "Requests today",
    value: "1,284",
    detail: "Sample activity",
    icon: Activity01Icon,
    tone: "info",
  },
  {
    label: "Relay health",
    value: "99.9%",
    detail: "Last 24 hours · sample",
    icon: CheckmarkCircle01Icon,
    tone: "safe",
  },
];

const creatorReviews = [
  {
    name: "Atlas Data Studio",
    initials: "AD",
    category: "Research data",
    submitted: "12 min ago",
    status: "Needs review",
  },
  {
    name: "Northstar Compute",
    initials: "NC",
    category: "Cloud computing",
    submitted: "38 min ago",
    status: "Needs review",
  },
  {
    name: "Greenline Signals",
    initials: "GS",
    category: "Market data",
    submitted: "Yesterday",
    status: "In progress",
  },
];

const platformEvents = [
  {
    title: "Creator account submitted",
    detail: "Atlas Data Studio · review requested",
    time: "12m",
  },
  {
    title: "Service health recovered",
    detail: "Northstar Compute · response returned",
    time: "34m",
  },
  { title: "Workspace created", detail: "Pax Labs · production", time: "2h" },
];

function MetricCard({ metric }: { metric: (typeof metrics)[number] }) {
  return (
    <article className={`card metric admin-metric metric-${metric.tone}`}>
      <div className="metric-label">
        <span>{metric.label}</span>
        <HugeiconsIcon
          icon={metric.icon}
          size={19}
          color="currentColor"
          strokeWidth={1.7}
          aria-hidden="true"
        />
      </div>
      <div className="metric-value">{metric.value}</div>
      <div className="metric-foot">{metric.detail}</div>
    </article>
  );
}

export default function AdminDashboardPage() {
  return (
    <div className="page admin-dashboard">
      <header className="page-head">
        <div>
          <div className="eyebrow">PaxRelay platform administration</div>
          <h1 className="page-title">A clear view of the network.</h1>
          <p className="page-subtitle">
            Review creator access, keep workspaces healthy, and follow activity
            across the platform.
          </p>
        </div>
        <div className="page-actions">
          <Link className="button primary" href={"/admin/settlements" as Route}>
            <HugeiconsIcon
              icon={Invoice01Icon}
              size={16}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
            Review settlements
          </Link>
          <Link className="button" href="#creators">
            <HugeiconsIcon
              icon={UserIcon}
              size={16}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
            View creator queue
          </Link>
        </div>
      </header>

      <div className="preview-note" role="note">
        <span className="preview-note-mark" aria-hidden="true">
          i
        </span>
        <p>
          <strong>Preview dashboard.</strong> Figures and activity below are
          sample data; platform controls are not connected yet.
        </p>
      </div>

      <section className="grid metrics" aria-label="Platform summary">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      <div className="grid two admin-dashboard-grid">
        <section className="card" id="creators">
          <div className="card-head">
            <div>
              <h2 className="card-title">Creator reviews</h2>
              <p className="card-description">
                Check new provider accounts before they go live.
              </p>
            </div>
            <span className="status pending">3 to review</span>
          </div>
          <div className="table-wrap">
            <table className="data-table admin-review-table">
              <thead>
                <tr>
                  <th>Creator</th>
                  <th>Category</th>
                  <th>Submitted</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {creatorReviews.map((creator) => (
                  <tr key={creator.name}>
                    <td>
                      <div className="agent-cell">
                        <span className="agent-avatar blue">
                          {creator.initials}
                        </span>
                        <span className="primary-cell">{creator.name}</span>
                      </div>
                    </td>
                    <td>{creator.category}</td>
                    <td>{creator.submitted}</td>
                    <td>
                      <span
                        className={`status ${creator.status === "Needs review" ? "pending" : "routing"}`}
                      >
                        {creator.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card" id="health">
          <div className="card-head">
            <div>
              <h2 className="card-title">Platform health</h2>
              <p className="card-description">
                A quick view of the services behind each request.
              </p>
            </div>
            <span className="status settled">All systems normal</span>
          </div>
          <div className="health-list">
            <div className="health-row">
              <span className="health-indicator good" />
              <span>
                <strong>Request gateway</strong>
                <small>Receiving and routing requests</small>
              </span>
              <b>Healthy</b>
            </div>
            <div className="health-row">
              <span className="health-indicator good" />
              <span>
                <strong>Policy checks</strong>
                <small>Checking limits before payment</small>
              </span>
              <b>Healthy</b>
            </div>
            <div className="health-row">
              <span className="health-indicator watch" />
              <span>
                <strong>Payment connection</strong>
                <small>Demo settlement mode is active</small>
              </span>
              <b>Demo</b>
            </div>
            <div className="health-row">
              <span className="health-indicator good" />
              <span>
                <strong>Receipt records</strong>
                <small>Keeping a record of each result</small>
              </span>
              <b>Healthy</b>
            </div>
          </div>
        </section>

        <section className="card" id="workspaces">
          <div className="card-head">
            <div>
              <h2 className="card-title">Workspaces</h2>
              <p className="card-description">
                Organisations using the PaxRelay demo.
              </p>
            </div>
            <span className="card-meta">SAMPLE DIRECTORY</span>
          </div>
          <div className="workspace-list">
            <div>
              <span className="workspace-avatar">PL</span>
              <span>
                <strong>Pax Labs</strong>
                <small>Production · 12 agents</small>
              </span>
              <span className="status settled">Active</span>
            </div>
            <div>
              <span className="workspace-avatar workspace-avatar-ember">
                AT
              </span>
              <span>
                <strong>Atlas Research</strong>
                <small>Sandbox · 4 agents</small>
              </span>
              <span className="status settled">Active</span>
            </div>
            <div>
              <span className="workspace-avatar workspace-avatar-violet">
                NL
              </span>
              <span>
                <strong>Northstar Labs</strong>
                <small>Sandbox · 7 agents</small>
              </span>
              <span className="status pending">Setup</span>
            </div>
          </div>
        </section>

        <section className="card" id="activity">
          <div className="card-head">
            <div>
              <h2 className="card-title">Recent platform activity</h2>
              <p className="card-description">
                Events from the sample platform feed.
              </p>
            </div>
            <HugeiconsIcon
              icon={Notification03Icon}
              size={18}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
          </div>
          <div className="platform-events">
            {platformEvents.map((event) => (
              <div className="activity-row" key={event.title}>
                <span className="activity-icon">
                  <HugeiconsIcon
                    icon={Notification03Icon}
                    size={15}
                    color="currentColor"
                    strokeWidth={1.7}
                    aria-hidden="true"
                  />
                </span>
                <span className="activity-copy">
                  <strong>{event.title}</strong>
                  <span>{event.detail}</span>
                </span>
                <span className="activity-time">{event.time}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="card admin-settings-card" id="settings">
          <div className="card-head">
            <div>
              <h2 className="card-title">Admin controls</h2>
              <p className="card-description">
                Platform-wide settings will live here.
              </p>
            </div>
            <HugeiconsIcon
              icon={Settings01Icon}
              size={18}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
          </div>
          <div className="settings-placeholder">
            <p>
              Role permissions, provider onboarding rules, and service review
              settings are not connected in this demo.
            </p>
            <Link className="button" href="/dashboard">
              Open the PaxRelay workspace
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
