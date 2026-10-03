"use client";

import { useState } from "react";
import { useAnalytics } from "@/hooks/use-analytics";
import { ScopedApiKeyAccess } from "@/components/scoped-api-key-access";

function formatAmount(amountAtomic: number, currency: string, decimals: number) {
  const amount = amountAtomic / 10 ** decimals;
  if (!Number.isFinite(amount)) return `— ${currency}`;

  return `${new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  }).format(amount)} ${currency}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

export function AnalyticsDashboard() {
  const [apiKey, setApiKey] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);
  const { data, error, loading } = useAnalytics(apiKey, reloadVersion);

  function clearKey() {
    setApiKey("");
  }

  const spend = data?.spend;
  const averageAmount = spend?.transaction_count
    ? spend.total_amount_atomic / spend.transaction_count
    : 0;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Operational intelligence</div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-subtitle">
            See committed spend and the capabilities your agents used over the
            last 30 days.
          </p>
        </div>
        {data ? (
          <button
            className="button primary"
            type="button"
            onClick={() => setReloadVersion((version) => version + 1)}
            disabled={loading}
          >
            {loading ? "Refreshing…" : "Refresh data"}
          </button>
        ) : null}
      </header>

      <ScopedApiKeyAccess
        scope="analytics:read"
        actionLabel="Load analytics"
        apiKey={apiKey}
        connected={Boolean(data)}
        loading={loading}
        error={error}
        onConnect={setApiKey}
        onDisconnect={clearKey}
      />

      {error ? (
        <div className="data-access-error" role="alert">
          <p>{error}</p>
          <button
            className="button"
            type="button"
            onClick={() => setReloadVersion((version) => version + 1)}
            disabled={loading}
          >
            Try again
          </button>
        </div>
      ) : null}

      {!apiKey ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">
            API
          </div>
          <div>
            <h2>Your workspace data will appear here</h2>
            <p>
              Connect a key to see spend totals and a breakdown by capability.
              No sample figures are shown on this page.
            </p>
          </div>
        </section>
      ) : loading && !data ? (
        <section className="card data-access-placeholder" aria-live="polite">
          <div className="data-access-mark" aria-hidden="true">
            …
          </div>
          <div>
            <h2>Loading workspace analytics</h2>
            <p>Fetching the last 30 days of committed spend.</p>
          </div>
        </section>
      ) : data ? (
        <>
          <div className="analytics-period" aria-live="polite">
            <span className="status neutral">Live API data</span>
            <span>
              {formatDate(spend!.start_date)} – {formatDate(spend!.end_date)}
            </span>
          </div>

          <div className="analytics-metrics">
            <article className="card metric metric-relay">
              <div className="metric-label">
                Committed spend <span>30D</span>
              </div>
              <div className="metric-value">
                {formatAmount(
                  spend!.total_amount_atomic,
                  spend!.currency,
                  spend!.decimals,
                )}
              </div>
              <div className="metric-foot">Verified or settled payments</div>
            </article>
            <article className="card metric">
              <div className="metric-label">
                Paid requests <span>30D</span>
              </div>
              <div className="metric-value">
                {new Intl.NumberFormat().format(spend!.transaction_count)}
              </div>
              <div className="metric-foot">Requests with committed payment</div>
            </article>
            <article className="card metric">
              <div className="metric-label">
                Average request cost <span>30D</span>
              </div>
              <div className="metric-value">
                {formatAmount(averageAmount, spend!.currency, spend!.decimals)}
              </div>
              <div className="metric-foot">Spend divided by paid requests</div>
            </article>
          </div>

          <section className="card analytics-breakdown">
            <header className="card-head">
              <div>
                <h2 className="card-title">Spend by capability</h2>
                <p className="card-description">
                  The highest-spend capabilities in this workspace during the
                  selected period.
                </p>
              </div>
              <span className="card-meta">
                {data.capabilities.length}{" "}
                {data.capabilities.length === 1 ? "capability" : "capabilities"}
              </span>
            </header>
            {data.capabilities.length === 0 ? (
              <div className="data-access-empty">
                <h3>No committed spend in this period</h3>
                <p>
                  Capability totals will appear after a paid request completes.
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Capability</th>
                      <th scope="col">Paid requests</th>
                      <th scope="col">Committed spend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.capabilities.map((item) => (
                      <tr key={item.capability}>
                        <td className="primary-cell mono">{item.capability}</td>
                        <td>{new Intl.NumberFormat().format(item.call_count)}</td>
                        <td className="amount">
                          {formatAmount(
                            item.total_amount_atomic,
                            item.currency,
                            item.decimals,
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
