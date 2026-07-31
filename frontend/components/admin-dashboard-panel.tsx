import Link from "next/link";

import {
  summarizeDashboardSnapshot,
  type DashboardSnapshot,
  type DashboardSummary,
  type DashboardSummaryCard,
} from "@/lib/admin-observability";

type Props = {
  snapshot: DashboardSnapshot;
  from: string;
  to: string;
};

function toneClass(tone: DashboardSummaryCard["tone"]): string {
  switch (tone) {
    case "success":
      return "summary-card summary-card-success";
    case "warning":
      return "summary-card summary-card-warning";
    case "danger":
      return "summary-card summary-card-danger";
    default:
      return "summary-card";
  }
}

function qualityPercent(count: number, total: number): string {
  if (total <= 0) {
    return "0%";
  }
  return `${Math.round((count / total) * 100)}%`;
}

function RunRow({ run }: { run: DashboardSummary["recentRuns"][number] }) {
  return (
    <Link className="list-row run-link" href={`/admin/runs/${encodeURIComponent(run.runId)}`}>
      <div>
        <div className="row-title">
          <strong>{run.headline}</strong>
          <span className="mini-pill">{run.statusLabel}</span>
        </div>
        <div className="row-metadata">
          {run.stageLabel} | {run.nodeLabel}
        </div>
        <div className="row-metadata">
          requester {run.requesterLabel} | updated {run.activityLabel}
        </div>
      </div>
      <div className="row-side">
        <span>{run.periodLabel}</span>
        <span>{run.badges.length > 0 ? run.badges.join(" | ") : "no flags"}</span>
      </div>
    </Link>
  );
}

export function AdminDashboardPanel({ snapshot, from, to }: Props) {
  const summary = summarizeDashboardSnapshot(snapshot);
  const qualityTotal = summary.qualityBuckets.reduce((total, bucket) => total + bucket.count, 0);

  return (
    <main className="app-shell">
      <div className="page dashboard-page">
        <header className="hero hero-dashboard">
          <div>
            <p className="kicker">Admin Dashboard</p>
            <h1 className="title">Agent observability</h1>
            <p className="lede">
              Read-only dashboard for run health, recent activity, and quality signals across the
              selected window.
            </p>
          </div>
          <div className="hero-meta">
            <span className="status-pill">dashboard</span>
            <span className="meta-chip">request {snapshot.requestId ?? "n/a"}</span>
            <Link className="meta-chip link-chip" href="/admin/runs">
              Open run list
            </Link>
            <Link className="meta-chip link-chip" href="/admin/configuration">
              Open configuration
            </Link>
          </div>
        </header>

        <section className="panel filters-panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Window</p>
              <h2>Dashboard filters</h2>
            </div>
            <span className="mono-chip">{summary.windowLabel}</span>
          </div>
          <form className="form-grid form-grid-3" action="/admin/dashboard" method="get">
            <label className="field">
              <span className="field-label">From</span>
              <input
                className="text-input"
                type="date"
                name="from"
                defaultValue={from || snapshot.window.from || ""}
              />
            </label>
            <label className="field">
              <span className="field-label">To</span>
              <input
                className="text-input"
                type="date"
                name="to"
                defaultValue={to || snapshot.window.to || ""}
              />
            </label>
            <div className="panel-actions filter-actions field-span-3">
              <button className="primary-button" type="submit">
                Refresh dashboard
              </button>
              <Link className="secondary-button" href="/admin/dashboard">
                Reset
              </Link>
            </div>
          </form>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Metrics</p>
              <h2>Window summary</h2>
            </div>
            <span className="mono-chip">{summary.metricCards.length} cards</span>
          </div>
          <div className="summary-grid summary-grid-3">
            {summary.metricCards.map((card) => (
              <div className={toneClass(card.tone)} key={card.label}>
                <span className="summary-label">{card.label}</span>
                <strong>{card.value}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-8">
            <div className="panel-head">
              <div>
                <p className="section-label">Runs</p>
                <h2>Recent executions</h2>
              </div>
              <span className="mono-chip">{summary.recentRuns.length} rows</span>
            </div>
            <div className="stack">
              {summary.recentRuns.length > 0 ? (
                summary.recentRuns.map((run) => <RunRow key={run.runId} run={run} />)
              ) : (
                <div className="empty-state">No runs in the selected window</div>
              )}
            </div>
          </article>

          <article className="panel panel-span-4">
            <div className="panel-head">
              <div>
                <p className="section-label">Quality</p>
                <h2>Result mix</h2>
              </div>
              <span className="mono-chip">{qualityTotal} total</span>
            </div>
            <div className="stack">
              {summary.qualityBuckets.length > 0 ? (
                summary.qualityBuckets.map((bucket) => (
                  <div className="quality-row" key={bucket.label}>
                    <div className="row-title">
                      <strong>{bucket.label}</strong>
                      <span className="mini-pill">{bucket.count}</span>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-fill"
                        style={{
                          width: qualityPercent(bucket.count, qualityTotal),
                        }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty-state">No quality breakdown available</div>
              )}
            </div>

            <div className="subpanel">
              <div className="panel-head">
                <div>
                  <p className="section-label">Tokens</p>
                  <h3>Usage summary</h3>
                </div>
              </div>
              <div className="summary-grid">
                {summary.tokenSummary.map((item) => (
                  <div className="summary-card" key={item.label}>
                    <span className="summary-label">{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}
