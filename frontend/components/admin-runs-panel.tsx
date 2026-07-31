import Link from "next/link";

import {
  buildRunListSearchParams,
  summarizeRunListRow,
  type RunListFilters,
  type RunListPage,
  type RunListSummaryRow,
} from "@/lib/admin-observability";

type Props = {
  page: RunListPage;
  filters: RunListFilters;
};

function triStateValue(value: boolean | null | undefined): string {
  if (value === true) {
    return "true";
  }
  if (value === false) {
    return "false";
  }
  return "any";
}

function toneLabel(row: RunListSummaryRow): string {
  if (row.badges.length > 0) {
    return row.badges.join(" | ");
  }
  return "no flags";
}

function RunRow({ run }: { run: RunListSummaryRow }) {
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
          requester {run.requesterLabel} | activity {run.activityLabel}
        </div>
      </div>
      <div className="row-side">
        <span>{run.periodLabel}</span>
        <span>{toneLabel(run)}</span>
      </div>
    </Link>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-card">
      <span className="summary-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function AdminRunsPanel({ page, filters }: Props) {
  const rows = page.items.map((row) => summarizeRunListRow(row));
  const nextHref = page.nextCursor
    ? `/admin/runs?${buildRunListSearchParams({ ...filters, cursor: page.nextCursor })}`
    : null;
  const resetHref = `/admin/runs?${buildRunListSearchParams({ ...filters, cursor: null })}`;

  return (
    <main className="app-shell">
      <div className="page runs-page">
        <header className="hero hero-runs">
          <div>
            <p className="kicker">Admin Runs</p>
            <h1 className="title">Run list</h1>
            <p className="lede">
              Filter and inspect executions, then jump directly into the detailed trace for any
              run.
            </p>
          </div>
          <div className="hero-meta">
            <span className="status-pill">runs</span>
            <span className="meta-chip">request {page.requestId ?? "n/a"}</span>
            <span className="meta-chip">page size {page.limit}</span>
            <Link className="meta-chip link-chip" href="/admin/dashboard">
              Open dashboard
            </Link>
          </div>
        </header>

        <section className="panel filters-panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Filters</p>
              <h2>Search executions</h2>
            </div>
            <span className="mono-chip">
              {page.hasMore ? "more rows available" : "last page"}
            </span>
          </div>
          <form className="form-grid form-grid-3" action="/admin/runs" method="get">
            <label className="field">
              <span className="field-label">Status</span>
              <input
                className="text-input"
                name="status"
                defaultValue={filters.status ?? ""}
                placeholder="completed, waiting, failed"
              />
            </label>
            <label className="field">
              <span className="field-label">Requester</span>
              <input
                className="text-input"
                name="requester_id"
                defaultValue={filters.requesterId ?? ""}
                placeholder="local-demo"
              />
            </label>
            <label className="field">
              <span className="field-label">Limit</span>
              <select className="text-input" name="limit" defaultValue={String(filters.limit ?? page.limit)}>
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Created from</span>
              <input
                className="text-input"
                type="date"
                name="created_from"
                defaultValue={filters.createdFrom ?? ""}
              />
            </label>
            <label className="field">
              <span className="field-label">Created to</span>
              <input
                className="text-input"
                type="date"
                name="created_to"
                defaultValue={filters.createdTo ?? ""}
              />
            </label>
            <label className="field">
              <span className="field-label">Period start</span>
              <input
                className="text-input"
                type="date"
                name="period_start"
                defaultValue={filters.periodStart ?? ""}
              />
            </label>
            <label className="field">
              <span className="field-label">Period end</span>
              <input
                className="text-input"
                type="date"
                name="period_end"
                defaultValue={filters.periodEnd ?? ""}
              />
            </label>
            <label className="field">
              <span className="field-label">HITL</span>
              <select
                className="text-input"
                name="has_human_input"
                defaultValue={triStateValue(filters.hasHumanInput)}
              >
                <option value="any">any</option>
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Retries</span>
              <select
                className="text-input"
                name="has_retry"
                defaultValue={triStateValue(filters.hasRetry)}
              >
                <option value="any">any</option>
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Partial failure</span>
              <select
                className="text-input"
                name="has_partial_failure"
                defaultValue={triStateValue(filters.hasPartialFailure)}
              >
                <option value="any">any</option>
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            </label>
            <div className="panel-actions filter-actions field-span-3">
              <button className="primary-button" type="submit">
                Apply filters
              </button>
              <Link className="secondary-button" href={resetHref}>
                Reset
              </Link>
            </div>
          </form>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Page</p>
              <h2>Loaded executions</h2>
            </div>
            <span className="mono-chip">{rows.length} rows</span>
          </div>
          <div className="summary-grid summary-grid-3 compact-grid">
            <SummaryCard label="Loaded rows" value={String(rows.length)} />
            <SummaryCard label="Page size" value={String(page.limit)} />
            <SummaryCard label="Next cursor" value={page.nextCursor ?? "n/a"} />
          </div>
          <div className="stack">
            {rows.length > 0 ? (
              rows.map((run) => <RunRow key={run.runId} run={run} />)
            ) : (
              <div className="empty-state">No executions matched the current filters</div>
            )}
          </div>
          <div className="pagination-bar">
            <span className="mono-chip">request {page.requestId ?? "n/a"}</span>
            <div className="panel-actions">
              <Link className="secondary-button" href={resetHref}>
                First page
              </Link>
              {nextHref ? (
                <Link className="primary-button" href={nextHref}>
                  Load next page
                </Link>
              ) : (
                <button className="primary-button" type="button" disabled>
                  No more rows
                </button>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
