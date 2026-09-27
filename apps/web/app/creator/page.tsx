import type { Metadata } from "next";
import Link from "next/link";
import { HugeiconsIcon } from "@hugeicons/react";
import {
  CheckmarkCircle01Icon,
  Invoice01Icon,
  Package01Icon,
  Notification03Icon,
  Settings01Icon,
  UserIcon,
  Wallet01Icon,
} from "@hugeicons/core-free-icons";

export const metadata: Metadata = { title: "Creator dashboard" };

const metrics = [
  {
    label: "Published services",
    value: "04",
    detail: "3 live · 1 paused",
    icon: Package01Icon,
    tone: "safe",
  },
  {
    label: "Requests today",
    value: "128",
    detail: "Sample activity",
    icon: Notification03Icon,
    tone: "info",
  },
  {
    label: "Payments recorded",
    value: "$26.40",
    detail: "Today · USDX sample total",
    icon: Wallet01Icon,
    tone: "relay",
  },
  {
    label: "Service availability",
    value: "99.4%",
    detail: "Last 7 days · sample",
    icon: CheckmarkCircle01Icon,
    tone: "safe",
  },
];

const services = [
  {
    name: "Atlas Search API",
    description: "Verified market and research data",
    calls: "842",
    status: "Live",
  },
  {
    name: "Company Registry Lookup",
    description: "Business identity checks",
    calls: "216",
    status: "Live",
  },
  {
    name: "Document Extractor",
    description: "Structured document processing",
    calls: "104",
    status: "Live",
  },
  {
    name: "Legacy Data Feed",
    description: "Historical data endpoint",
    calls: "—",
    status: "Paused",
  },
];

const requests = [
  {
    agent: "Research Runner",
    service: "Atlas Search API",
    amount: "0.024 USDX",
    state: "Completed",
    time: "2 min ago",
  },
  {
    agent: "Treasury Scout",
    service: "Company Registry Lookup",
    amount: "0.010 USDX",
    state: "Completed",
    time: "9 min ago",
  },
  {
    agent: "Support Triage",
    service: "Document Extractor",
    amount: "0.018 USDX",
    state: "In progress",
    time: "14 min ago",
  },
];

function MetricCard({ metric }: { metric: (typeof metrics)[number] }) {
  return (
    <article className={`card metric creator-metric metric-${metric.tone}`}>
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

export default function CreatorDashboardPage() {
  return (
    <div className="page creator-dashboard">
      <header className="page-head">
        <div>
          <div className="eyebrow">Creator workspace · Atlas Data Studio</div>
          <h1 className="page-title">Your services, in one view.</h1>
          <p className="page-subtitle">
            Keep services available, follow incoming requests, and find the
            payment record for each completed job.
          </p>
        </div>
        <div className="page-actions">
          <Link className="button" href="#requests">
            View requests
          </Link>
          <Link className="button primary" href="#services">
            <HugeiconsIcon
              icon={Package01Icon}
              size={16}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
            Manage services
          </Link>
        </div>
      </header>

      <div className="preview-note" role="note">
        <span className="preview-note-mark" aria-hidden="true">
          i
        </span>
        <p>
          <strong>Preview dashboard.</strong> The services, request history, and
          payment amounts shown here are sample data.
        </p>
      </div>

      <section className="grid metrics" aria-label="Creator summary">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      <div className="grid two creator-dashboard-grid">
        <section className="card" id="services">
          <div className="card-head">
            <div>
              <h2 className="card-title">Your services</h2>
              <p className="card-description">
                Services that agents can request from your team.
              </p>
            </div>
            <span className="card-meta">4 SERVICES</span>
          </div>
          <div className="table-wrap">
            <table className="data-table creator-service-table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Requests · 7d</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {services.map((service) => (
                  <tr key={service.name}>
                    <td>
                      <span className="cell-stack">
                        <strong>{service.name}</strong>
                        <span>{service.description}</span>
                      </span>
                    </td>
                    <td className="amount">{service.calls}</td>
                    <td>
                      <span
                        className={`status ${service.status === "Live" ? "settled" : "paused"}`}
                      >
                        {service.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card" id="requests">
          <div className="card-head">
            <div>
              <h2 className="card-title">Recent requests</h2>
              <p className="card-description">
                Work requested from your services.
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
          <div className="creator-request-list">
            {requests.map((request) => (
              <article
                className="creator-request"
                key={`${request.agent}-${request.time}`}
              >
                <span className="request-mark">
                  <HugeiconsIcon
                    icon={UserIcon}
                    size={17}
                    color="currentColor"
                    strokeWidth={1.7}
                    aria-hidden="true"
                  />
                </span>
                <div className="creator-request-copy">
                  <div className="creator-request-heading">
                    <strong>{request.service}</strong>
                    <span
                      className={`status ${request.state === "Completed" ? "verified" : "routing"}`}
                    >
                      {request.state}
                    </span>
                  </div>
                  <span>
                    {request.agent} · {request.amount}
                  </span>
                  <small>{request.time}</small>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="card" id="receipts">
          <div className="card-head">
            <div>
              <h2 className="card-title">Payment records</h2>
              <p className="card-description">
                Receipts that show what happened after a request.
              </p>
            </div>
            <span className="card-meta">RECENT</span>
          </div>
          <div className="receipt-list">
            <div className="receipt-row">
              <span className="receipt-symbol">
                <HugeiconsIcon
                  icon={Invoice01Icon}
                  size={15}
                  color="currentColor"
                  strokeWidth={1.7}
                  aria-hidden="true"
                />
              </span>
              <span>
                <strong>rcpt_81A4...9KD</strong>
                <small>Atlas Search API · 0.024 USDX</small>
              </span>
              <span className="status verified">Verified</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-symbol">↗</span>
              <span>
                <strong>rcpt_703B...2QF</strong>
                <small>Company Registry Lookup · 0.010 USDX</small>
              </span>
              <span className="status verified">Verified</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-symbol">↗</span>
              <span>
                <strong>rcpt_6C20...1LA</strong>
                <small>Document Extractor · 0.018 USDX</small>
              </span>
              <span className="status routing">Recording</span>
            </div>
          </div>
        </section>

        <section className="card creator-profile-card" id="profile">
          <div className="card-head">
            <div>
              <h2 className="card-title">Provider profile</h2>
              <p className="card-description">
                Information agents see before using your services.
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
          <div className="profile-summary">
            <span className="profile-monogram">AD</span>
            <div>
              <strong>Atlas Data Studio</strong>
              <span>Research data · Nigeria</span>
            </div>
          </div>
          <div className="profile-note">
            <HugeiconsIcon
              icon={Settings01Icon}
              size={16}
              color="currentColor"
              strokeWidth={1.7}
              aria-hidden="true"
            />
            <p>
              Provider profile editing and service publishing are visual
              previews and are not connected to an account yet.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
