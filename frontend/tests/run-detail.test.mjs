import assert from "node:assert/strict";
import test from "node:test";

import { getRunStatusLabel, isTerminalRunStatus, summarizeRunDetail } from "../lib/run-detail.js";

const sampleDetail = {
  approvals: [{}, {}],
  artifacts: [{}, {}, {}],
  current_node: "complete_run",
  current_stage: "succeeded",
  graph_version: "weekly_report.v1",
  is_terminal: true,
  period_end: "2026-07-27",
  period_key: "2026-W30",
  period_start: "2026-07-20",
  polling_interval_ms: 5000,
  project_id: "project-1",
  refs: {
    approved_publish_plan_ref: "plan-1",
    artifact_refs: ["artifact-1"],
    operation_refs: ["operation-1"],
    publish_plan_ref: "plan-1",
    report_version_ref: "report-1",
  },
  requester_id: "local-demo",
  run_id: "run-1",
  should_poll: false,
  side_effects: [{}, {}, {}],
  status: "completed",
  tools: [{}, {}],
  approval_revision: 2,
  approval_status: "approved",
  error_code: null,
  error_summary: null,
  timestamps: {
    created_at: "2026-07-29T00:00:00Z",
    latest_activity_at: "2026-07-29T00:10:00Z",
    completed_at: "2026-07-29T00:10:00Z",
  },
};

test("terminal states stop polling", () => {
  assert.equal(isTerminalRunStatus("completed"), true);
  assert.equal(isTerminalRunStatus("waiting"), false);
  assert.equal(getRunStatusLabel("blocked"), "Blocked");

  const summary = summarizeRunDetail(sampleDetail);
  assert.equal(summary.isTerminal, true);
  assert.equal(summary.shouldPoll, false);
  assert.equal(summary.pollingLabel, "Polling paused");
  assert.equal(summary.toolsCount, 2);
  assert.equal(summary.artifactsCount, 3);
});

test("live states keep polling", () => {
  const summary = summarizeRunDetail({
    ...sampleDetail,
    is_terminal: false,
    should_poll: true,
    status: "waiting",
    current_stage: "waiting_publish_approval",
  });

  assert.equal(summary.isTerminal, false);
  assert.equal(summary.shouldPoll, true);
  assert.match(summary.pollingLabel, /Auto refresh/);
});
