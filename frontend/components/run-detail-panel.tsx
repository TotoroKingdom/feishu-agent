"use client";

import { useEffect, useState } from "react";

import { isTerminalRunStatus, summarizeRunDetail, type RunDetailView } from "@/lib/run-detail";

type Props = {
  initialDetail: RunDetailView;
  requestId: string;
};

type PanelState = {
  detail: RunDetailView;
  updatedAt: string;
  error: string | null;
};

function formatIso(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Shanghai",
  }).format(parsed);
}

function renderSummaryValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value, null, 2);
}

async function fetchRunDetail(runId: string): Promise<RunDetailView> {
  const response = await fetch(`/api/v1/admin/runs/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Unable to refresh run detail (${response.status})`);
  }
  const payload = (await response.json()) as { data: RunDetailView };
  return payload.data;
}

export function RunDetailPanel({ initialDetail, requestId }: Props) {
  const [state, setState] = useState<PanelState>({
    detail: initialDetail,
    updatedAt: new Date().toISOString(),
    error: null,
  });

  const summary = summarizeRunDetail(state.detail);

  useEffect(() => {
    if (isTerminalRunStatus(state.detail.status) || !state.detail.should_poll) {
      return;
    }

    let cancelled = false;

    const refresh = async () => {
      try {
        const next = await fetchRunDetail(state.detail.run_id);
        if (!cancelled) {
          setState({
            detail: next,
            updatedAt: new Date().toISOString(),
            error: null,
          });
        }
      } catch (error) {
        if (!cancelled) {
          setState((current) => ({
            ...current,
            error: error instanceof Error ? error.message : "Refresh failed",
          }));
        }
      }
    };

    const timer = window.setInterval(refresh, state.detail.polling_interval_ms);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    state.detail.current_stage,
    state.detail.polling_interval_ms,
    state.detail.run_id,
    state.detail.should_poll,
    state.detail.status,
  ]);

  return (
    <main className="app-shell">
      <div className="page">
        <header className="hero">
          <div>
            <p className="kicker">Run Detail</p>
            <h1 className="title">{summary.headline}</h1>
            <p className="lede">
              Read-only execution view with current node, approval records, tool summaries,
              artifacts, and side effects.
            </p>
          </div>
          <div className="hero-meta">
            <span className="status-pill">{summary.statusLabel}</span>
            <span className="meta-chip">{summary.pollingLabel}</span>
            <span className="meta-chip">request {requestId || "n/a"}</span>
            <span className="meta-chip">updated {formatIso(state.updatedAt)}</span>
          </div>
        </header>

        {state.error ? <section className="inline-alert">{state.error}</section> : null}

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Overview</p>
              <h2>Current state</h2>
            </div>
            <span className="mono-chip">{state.detail.current_stage}</span>
          </div>
          <div className="grid grid-4">
            <SummaryCard label="Run ID" value={state.detail.run_id} />
            <SummaryCard label="Current Node" value={state.detail.current_node ?? "n/a"} />
            <SummaryCard label="Approval" value={state.detail.approval_status} />
            <SummaryCard label="Poll" value={summary.pollingLabel} />
          </div>
          <div className="detail-grid">
            <DetailRow label="Project" value={state.detail.project_id} />
            <DetailRow
              label="Period"
              value={`${state.detail.period_key} | ${state.detail.period_start} -> ${state.detail.period_end}`}
            />
            <DetailRow label="Requester" value={state.detail.requester_id} />
            <DetailRow label="Graph" value={state.detail.graph_version} />
            <DetailRow label="Current Node" value={state.detail.current_node ?? "n/a"} />
            <DetailRow
              label="Last Update"
              value={formatIso(state.detail.timestamps.latest_activity_at ?? state.detail.timestamps.created_at)}
            />
          </div>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-7">
            <div className="panel-head">
              <div>
                <p className="section-label">Approvals</p>
                <h2>HITL records</h2>
              </div>
              <span className="mono-chip">{summary.approvalsCount} items</span>
            </div>
            <div className="stack">
              {state.detail.approvals.map((approval) => (
                <div className="list-row" key={`${approval.approval_type}-${approval.revision}`}>
                  <div>
                    <div className="row-title">
                      <strong>{approval.approval_type}</strong>
                      <span className="mini-pill">{approval.status}</span>
                    </div>
                    <div className="row-metadata">
                      revision {approval.revision} | challenge {approval.challenge_id} | request{" "}
                      {approval.request_payload_hash.slice(0, 10)}
                    </div>
                  </div>
                  <div className="row-side">
                    <span>{approval.requested_from.join(", ") || "local-demo"}</span>
                    <span>{formatIso(approval.decided_at)}</span>
                  </div>
                </div>
              ))}
              {state.detail.approvals.length === 0 ? <EmptyState text="No approval records yet" /> : null}
            </div>
          </article>

          <article className="panel panel-span-5">
            <div className="panel-head">
              <div>
                <p className="section-label">Refs</p>
                <h2>Key refs</h2>
              </div>
            </div>
            <div className="ref-cloud">
              <RefChip label="Report" value={state.detail.refs.report_version_ref} />
              <RefChip label="Publish Plan" value={state.detail.refs.publish_plan_ref} />
              <RefChip label="Approved Plan" value={state.detail.refs.approved_publish_plan_ref} />
            </div>
            <div className="stack">
              <MiniSection
                title="Artifacts"
                items={state.detail.artifacts.map(
                  (artifact) => `${artifact.artifact_type} | ${artifact.external_id ?? artifact.operation_id}`,
                )}
              />
              <MiniSection
                title="Operations"
                items={state.detail.side_effects.map(
                  (operation) => `${operation.sequence}. ${operation.operation_type} | ${operation.status}`,
                )}
              />
            </div>
          </article>
        </section>

        <section className="panel-grid">
          <article className="panel panel-span-8">
            <div className="panel-head">
              <div>
                <p className="section-label">Tools</p>
                <h2>Tool summaries</h2>
              </div>
              <span className="mono-chip">{summary.toolsCount} calls</span>
            </div>
            <div className="stack">
              {state.detail.tools.map((tool) => (
                <div className="list-row" key={`${tool.node_execution_id}-${tool.attempt}`}>
                  <div>
                    <div className="row-title">
                      <strong>{tool.tool_name}</strong>
                      <span className="mini-pill">{tool.status}</span>
                    </div>
                    <div className="row-metadata">
                      node {tool.node_execution_id} | attempt {tool.attempt} | retryable{" "}
                      {String(tool.retryable)}
                    </div>
                  </div>
                  <div className="row-side">
                    <span>{tool.error_code ?? "ok"}</span>
                    <span>{tool.duration_ms ?? 0}ms</span>
                  </div>
                  <div className="summary-block">
                    <div>
                      <span className="summary-label">request</span>
                      <pre>{renderSummaryValue(tool.request_summary)}</pre>
                    </div>
                    <div>
                      <span className="summary-label">result</span>
                      <pre>{renderSummaryValue(tool.result_summary)}</pre>
                    </div>
                  </div>
                </div>
              ))}
              {state.detail.tools.length === 0 ? <EmptyState text="No tool calls yet" /> : null}
            </div>
          </article>

          <article className="panel panel-span-4">
            <div className="panel-head">
              <div>
                <p className="section-label">Artifacts</p>
                <h2>Artifacts</h2>
              </div>
              <span className="mono-chip">{summary.artifactsCount} items</span>
            </div>
            <div className="stack">
              {state.detail.artifacts.map((artifact) => (
                <div className="artifact-row" key={artifact.operation_id}>
                  <div className="row-title">
                    <strong>{artifact.artifact_type}</strong>
                    <span className="mini-pill">{artifact.status}</span>
                  </div>
                  <div className="row-metadata">{artifact.external_id ?? artifact.operation_id}</div>
                  <div className="row-metadata">{artifact.url ?? "n/a"}</div>
                  <div className="row-metadata">verified {formatIso(artifact.verified_at)}</div>
                </div>
              ))}
              {state.detail.artifacts.length === 0 ? <EmptyState text="No artifacts yet" /> : null}
            </div>
          </article>
        </section>

        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Errors</p>
              <h2>Errors and trace</h2>
            </div>
            <span className="mono-chip">{summary.sideEffectsCount} operations</span>
          </div>
          <div className="detail-grid">
            <DetailRow label="Error Code" value={state.detail.error_code ?? "none"} />
            <DetailRow label="Error Summary" value={state.detail.error_summary ?? "none"} />
            <DetailRow label="Polling" value={summary.pollingLabel} />
            <DetailRow label="Terminal" value={String(summary.isTerminal)} />
          </div>
        </section>
      </div>
    </main>
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

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RefChip({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="ref-chip">
      <span>{label}</span>
      <strong>{value ?? "n/a"}</strong>
    </div>
  );
}

function MiniSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mini-section">
      <span className="summary-label">{title}</span>
      <ul>
        {items.length > 0 ? items.map((item) => <li key={item}>{item}</li>) : <li>n/a</li>}
      </ul>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}
