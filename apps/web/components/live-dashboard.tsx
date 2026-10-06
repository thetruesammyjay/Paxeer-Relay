"use client";

import Link from "next/link";
import type { Route } from "next";
import { useApiSession } from "@/lib/api-session";
import {
  DASHBOARD_SCOPES,
  useLiveDashboard,
  type DashboardResource,
  type LiveDashboardData,
  type LiveDashboardMode,
} from "@/hooks/use-live-dashboard";
import type { Approval } from "@/hooks/use-approvals";
import type { ReceiptRecord } from "@/hooks/use-receipts";
import type { ServiceRecord } from "@/hooks/use-services";
import type { Transaction } from "@/hooks/use-transactions";

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function displayTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function money(atomic: string | number, decimals = 6, currency = "USDX"): string {
  let exact: bigint;
  try {
    exact = BigInt(atomic);
  } catch {
    return `— ${currency}`;
  }
  const negative = exact < 0n;
  const absolute = negative ? -exact : exact;
  const scale = 10n ** BigInt(decimals);
  const minorUnits = (absolute * 100n + scale / 2n) / scale;
  const whole = minorUnits / 100n;
  const fraction = (minorUnits % 100n).toString().padStart(2, "0");
  return `${negative ? "−" : ""}${whole.toLocaleString()}.${fraction} ${currency}`;
}

function stateTone(value: string): string {
  if (["active", "delivered", "succeeded", "verified", "settled_layerx", "anchored_l1"].includes(value)) {
    return "verified";
  }
  if (["failed", "unknown", "provider_error", "mismatch", "revoked", "inactive"].includes(value)) {
    return "denied";
  }
  if (["pending", "quoted", "approval_pending", "payment_required", "execution_reserved"].includes(value)) {
    return "pending";
  }
  return "neutral";
}

function stateLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function Metric({
  label,
  value,
  detail,
  tone = "relay",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className={`card metric metric-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">{detail}</div>
    </article>
  );
}

function ServiceRows({ services }: { services: ServiceRecord[] }) {
  if (!services.length) {
    return <p className="live-empty">No services are registered in this production project.</p>;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Service</th>
            <th scope="col">Protocol</th>
            <th scope="col">Health check</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {services.slice(0, 8).map((service) => {
            const check = service.health.last_check_passing;
            return (
              <tr key={service.id}>
                <td>
                  <span className="cell-stack">
                    <strong>{service.name}</strong>
                    <span>{service.capability}</span>
                  </span>
                </td>
                <td>{service.protocols.map(stateLabel).join(", ")}</td>
                <td>
                  <span className={`status ${check === true ? "verified" : check === false ? "denied" : "neutral"}`}>
                    {check === true ? "Passing" : check === false ? "Failing" : "Not checked"}
                  </span>
                  <small className="live-subcell">{displayTime(service.health.last_check_at)}</small>
                </td>
                <td>
                  <span className={`status ${stateTone(service.status)}`}>
                    {stateLabel(service.status)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RequestRows({ transactions }: { transactions: Transaction[] }) {
  if (!transactions.length) {
    return <p className="live-empty">No requests are recorded for this production project yet.</p>;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Request</th>
            <th scope="col">Agent</th>
            <th scope="col">Capability</th>
            <th scope="col">Payment</th>
            <th scope="col">Execution</th>
            <th scope="col">Created</th>
          </tr>
        </thead>
        <tbody>
          {transactions.slice(0, 8).map((transaction) => (
            <tr key={transaction.id}>
              <td><code title={transaction.id}>{shortId(transaction.id)}</code></td>
              <td><code title={transaction.agent_id}>{shortId(transaction.agent_id)}</code></td>
              <td>{transaction.capability}</td>
              <td><span className={`status ${stateTone(transaction.payment_state)}`}>{stateLabel(transaction.payment_state)}</span></td>
              <td><span className={`status ${stateTone(transaction.execution_state)}`}>{stateLabel(transaction.execution_state)}</span></td>
              <td>{displayTime(transaction.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ApprovalRows({ approvals }: { approvals: Approval[] }) {
  if (!approvals.length) {
    return <p className="live-empty">There are no pending approvals in this production project.</p>;
  }
  return (
    <div className="live-record-list">
      {approvals.slice(0, 5).map((approval) => (
        <article className="live-record-row" key={approval.id}>
          <span className="live-record-copy">
            <strong>{approval.capability}</strong>
            <span>{shortId(approval.agent_id)} · {money(approval.amount_atomic, approval.decimals, approval.currency)}</span>
            <small>Expires {displayTime(approval.expires_at)}</small>
          </span>
          <span className={`status ${stateTone(approval.status)}`}>{stateLabel(approval.status)}</span>
        </article>
      ))}
    </div>
  );
}

function ReceiptRows({ receipts }: { receipts: ReceiptRecord[] }) {
  if (!receipts.length) {
    return <p className="live-empty">No execution receipts have been issued in this production project yet.</p>;
  }
  return (
    <div className="live-record-list">
      {receipts.slice(0, 5).map((receipt) => (
        <article className="live-record-row" key={receipt.id}>
          <span className="live-record-copy">
            <strong>{receipt.capability}</strong>
            <span>{money(receipt.payment_amount, 6, receipt.payment_currency)} · {receipt.execution_latency_ms} ms</span>
            <small>{displayTime(receipt.issued_at)} · receipt {shortId(receipt.id)}</small>
          </span>
          <span className={`status ${stateTone(receipt.execution_status)}`}>
            {stateLabel(receipt.execution_status)}
          </span>
        </article>
      ))}
    </div>
  );
}

function ProviderRows({ providers }: { providers: NonNullable<LiveDashboardData["providers"]> }) {
  if (!providers.data?.length) {
    return <p className="live-empty">No provider profiles are registered in this production project.</p>;
  }
  return (
    <div className="live-record-list">
      {providers.data.slice(0, 8).map((provider) => (
        <article className="live-record-row" key={provider.id}>
          <span className="live-record-copy">
            <strong>{provider.name}</strong>
            <span>{provider.slug}</span>
            <small>{provider.wallet_address ? `Wallet ${shortId(provider.wallet_address)}` : "No payment wallet configured"}</small>
          </span>
          <span className={`status ${stateTone(provider.status)}`}>{stateLabel(provider.status)}</span>
        </article>
      ))}
    </div>
  );
}

function resourceProblem<T>(resource: DashboardResource<T>, scope: string): string | null {
  const problem = resource.problem;
  if (!problem) return null;
  if (problem.status === 403) return `Your project role or development key cannot read this section. It needs ${scope}.`;
  if (problem.status === 401) {
    return "Your workspace session expired or was revoked. Sign in again or reconnect the development key.";
  }
  if (problem.status === 429) {
    return "The API is rate limiting this project. Wait briefly, then refresh.";
  }
  if (problem.status === 0 || problem.status === null) return "The PaxRelay API could not be reached.";
  return `This section could not load (HTTP ${problem.status}).`;
}

function ResourceProblem<T>({ resource, scope }: { resource: DashboardResource<T>; scope: string }) {
  const message = resourceProblem(resource, scope);
  return message ? <p className="live-empty" role="status">{message}</p> : null;
}

export function LiveDashboard({ mode }: { mode: LiveDashboardMode }) {
  const session = useApiSession();
  const query = useLiveDashboard(session.apiKey, session.connectionVersion, mode);
  const title =
    mode === "admin"
      ? "Production operations"
      : mode === "creator"
        ? "Provider activity"
        : "Production workspace";
  const subtitle =
    mode === "admin"
      ? "Review live providers, service health, requests, and approvals for this project."
      : mode === "creator"
        ? "Follow your project’s services, recent requests, and execution receipts."
        : "Monitor production requests, spending, service health, and approvals.";
  const servicesResource = query.data?.services;
  const transactionsResource = query.data?.transactions;
  const approvalsResource = query.data?.approvals;
  const receiptsResource = query.data?.receipts;
  const providersResource = query.data?.providers;
  const spendResource = query.data?.spend;
  const services = servicesResource?.data ?? [];
  const transactions = transactionsResource?.data ?? [];
  const approvals = approvalsResource?.data ?? [];
  const receipts = receiptsResource?.data ?? [];
  const serviceCount = services.length;
  const healthyServices = services.filter(
    (service) => service.status === "active" && service.health.last_check_passing === true,
  ).length;
  const spend = spendResource?.data;
  const unavailableCount = query.data
    ? Object.values(query.data).filter((resource) => resource !== undefined && resource.problem !== null).length
    : 0;
  const resourceCount = query.data ? Object.keys(query.data).length : 0;

  return (
    <div className={`page live-dashboard live-dashboard-${mode}`}>
      <header className="page-head">
        <div>
          <div className="eyebrow">{session.workspace ? `Production project ${shortId(session.workspace.project_id)}` : "Production data"}</div>
          <h1 className="page-title">{title}</h1>
          <p className="page-subtitle">{subtitle}</p>
        </div>
        <div className="page-actions">
          {session.apiKey ? (
            <button
              className="button primary"
              type="button"
              onClick={() => void query.refetch()}
              disabled={query.isFetching}
            >
              {query.isFetching ? "Refreshing…" : "Refresh live data"}
            </button>
          ) : null}
          {mode === "admin" ? (
            <Link className="button" href={"/admin/settlements" as Route}>Settlement review</Link>
          ) : mode === "creator" ? (
            <Link className="button" href="/services">Manage services</Link>
          ) : (
            <Link className="button" href="/transactions">Open transactions</Link>
          )}
        </div>
      </header>

      {!session.apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">API</div>
          <div>
            <h2>Connect the production API to load this dashboard</h2>
            <p>
              Use <strong>Connect production API</strong> in the header. The API
              verifies the environment before the console requests tenant data.
              No sample or simulated figures are shown here.
            </p>
          </div>
        </section>
      ) : query.isPending ? (
        <section className="card data-access-placeholder" role="status">
          <div className="data-access-mark" aria-hidden="true">…</div>
          <div>
            <h2>Loading production data</h2>
            <p>Reading live workspace records from the production API.</p>
          </div>
        </section>
      ) : query.isError && !query.data ? (
        <section className="card live-dashboard-error" role="alert">
          <h2>Dashboard data is unavailable</h2>
          <p>{query.error instanceof Error ? query.error.message : "The production API could not load this dashboard."}</p>
          <button
            className="button"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            Try again
          </button>
        </section>
      ) : query.data ? (
        <>
          <div className="live-dashboard-status" aria-live="polite">
            <span className={`status ${unavailableCount === Object.keys(query.data).length ? "denied" : unavailableCount ? "pending" : "active"}`}>
              {resourceCount > 0 && unavailableCount === resourceCount ? "No data available" : unavailableCount ? "Partial live data" : "Live API data"}
            </span>
            <span>{query.isFetching ? "Refreshing" : `Updated ${displayTime(new Date(query.dataUpdatedAt).toISOString())}`}</span>
            {query.isError ? <span className="live-stale-note">Refresh failed; showing the last successful response.</span> : null}
          </div>

          <section className="grid metrics live-dashboard-metrics" aria-label="Live production metrics">
            <Metric
              label="Active services"
              value={servicesResource?.problem ? "—" : String(services.filter((service) => service.status === "active").length)}
              detail={servicesResource?.problem ? `Requires ${DASHBOARD_SCOPES.services}` : `${healthyServices} have a passing latest health check`}
              tone="safe"
            />
            <Metric
              label="Recent requests"
              value={transactionsResource?.problem ? "—" : String(transactions.length)}
              detail={transactionsResource?.problem ? `Requires ${DASHBOARD_SCOPES.transactions}` : "Latest tenant records returned by the API, up to 100"}
              tone="info"
            />
            {mode !== "creator" ? (
              <Metric
                label="Pending approvals"
                value={approvalsResource?.problem ? "—" : approvals.length === 100 ? "100+" : String(approvals.length)}
                detail={approvalsResource?.problem ? `Requires ${DASHBOARD_SCOPES.approvals}` : "Open requests in this production project"}
                tone="warn"
              />
            ) : null}
            <Metric
              label="Committed spend · 30 days"
              value={spend ? money(spend.total_amount_atomic, spend.decimals, spend.currency) : "—"}
              detail={spendResource?.problem ? `Requires ${DASHBOARD_SCOPES.spend}` : `${(spend?.transaction_count ?? 0).toLocaleString()} payments in the selected window`}
              tone="relay"
            />
          </section>

          {unavailableCount > 0 ? (
            <p className="live-dashboard-warning" role="status">
              {unavailableCount} live data section{unavailableCount === 1 ? " is" : "s are"} unavailable. Check the key&apos;s grants or refresh after the API recovers.
            </p>
          ) : null}

          <div className="grid two live-dashboard-grid">
            {mode !== "creator" ? (
              <section className="card" id="services">
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Service health</h2>
                    <p className="card-description">
                      {servicesResource?.problem ? `Live service data unavailable. Required access: ${DASHBOARD_SCOPES.services}.` : `${serviceCount.toLocaleString()} production services returned by the API. Routing requires an active service and a passing health check.`}
                    </p>
                  </div>
                  <Link className="card-meta" href="/services">Open services</Link>
                </div>
                {servicesResource?.problem ? <ResourceProblem resource={servicesResource} scope={DASHBOARD_SCOPES.services} /> : <ServiceRows services={services} />}
              </section>
            ) : (
              <section className="card" id="services">
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Project services</h2>
                    <p className="card-description">
                      Live service configuration and latest health observations for this project.
                    </p>
                  </div>
                  <Link className="card-meta" href="/services">Manage services</Link>
                </div>
                {servicesResource?.problem ? <ResourceProblem resource={servicesResource} scope={DASHBOARD_SCOPES.services} /> : <ServiceRows services={services} />}
              </section>
            )}

            {mode === "creator" ? (
              <section className="card" id="receipts">
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Recent execution receipts</h2>
                    <p className="card-description">
                      Provider, amount, timing, and status returned by the live API. Signatures are displayed in the Receipts page.
                    </p>
                  </div>
                  <Link className="card-meta" href="/receipts">Open receipts</Link>
                </div>
                {receiptsResource?.problem ? <ResourceProblem resource={receiptsResource} scope={DASHBOARD_SCOPES.receipts} /> : <ReceiptRows receipts={receipts} />}
              </section>
            ) : mode === "admin" ? (
              <section className="card" id="providers">
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Providers in this project</h2>
                    <p className="card-description">
                      Tenant-scoped provider records. This project API does not expose a cross-customer platform directory.
                    </p>
                  </div>
                  <Link className="card-meta" href="/providers">Open providers</Link>
                </div>
                {providersResource?.problem ? <ResourceProblem resource={providersResource} scope={DASHBOARD_SCOPES.providers} /> : <ProviderRows providers={providersResource!} />}
              </section>
            ) : (
              <section className="card" id="approvals">
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Approval queue</h2>
                    <p className="card-description">
                      Live policy exceptions waiting for an authorised decision.
                    </p>
                  </div>
                  <Link className="card-meta" href="/approvals">Review approvals</Link>
                </div>
                {approvalsResource?.problem ? <ResourceProblem resource={approvalsResource} scope={DASHBOARD_SCOPES.approvals} /> : <ApprovalRows approvals={approvals} />}
              </section>
            )}

            <section className="card" id="activity">
              <div className="card-head">
                <div>
                  <h2 className="card-title">Recent requests</h2>
                  <p className="card-description">
                    Request, payment, and provider execution states from the latest API records.
                  </p>
                </div>
                <Link className="card-meta" href="/transactions">Open transactions</Link>
              </div>
              {transactionsResource?.problem ? <ResourceProblem resource={transactionsResource} scope={DASHBOARD_SCOPES.transactions} /> : <RequestRows transactions={transactions} />}
            </section>

            {mode === "admin" ? (
              <section className="card" id="approvals">
                <div className="card-head">
                  <div>
                    <h2 className="card-title">Approval queue</h2>
                    <p className="card-description">Pending human decisions returned by the production API.</p>
                  </div>
                  <Link className="card-meta" href="/approvals">Review approvals</Link>
                </div>
                {approvalsResource?.problem ? <ResourceProblem resource={approvalsResource} scope={DASHBOARD_SCOPES.approvals} /> : <ApprovalRows approvals={approvals} />}
              </section>
            ) : null}

            {mode === "admin" ? (
              <section className="card live-scope-note">
                <h2 className="card-title">Production project scope</h2>
                <p>
                  Every figure on this page comes from the connected project and
                  its assigned permissions. Cross-organisation platform totals and
                  creator onboarding reviews are not exposed by the current API.
                </p>
              </section>
            ) : null}

            {mode === "creator" ? (
              <section className="card live-scope-note">
                <h2 className="card-title">Data access scope</h2>
                <p>
                  The current API grants access by production project, not by
                  individual creator account. This view includes records the
                  your current role can read in that project; use a read-only
                  role for each provider workspace.
                </p>
              </section>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
