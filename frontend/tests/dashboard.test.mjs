import assert from "node:assert/strict";
import test from "node:test";

import {
  buildDashboardSearchParams,
  getDefaultDashboardWindow,
  normalizeDashboardSnapshot,
  summarizeDashboardSnapshot,
} from "../lib/admin-observability.js";

test("dashboard helpers default to a 30-day window and summarize recent runs", () => {
  const window = getDefaultDashboardWindow(new Date("2026-07-30T12:00:00Z"));
  assert.equal(window.from, "2026-06-30");
  assert.equal(window.to, "2026-07-30");
  assert.equal(buildDashboardSearchParams(window), "from=2026-06-30&to=2026-07-30");

  const snapshot = normalizeDashboardSnapshot({
    from: "2026-07-01",
    to: "2026-07-30",
    recent_runs: [
      {
        run_id: "run-1",
        project_id: "project-1",
        period_key: "2026-W30",
        status: "completed",
        current_stage: "succeeded",
        current_node: "complete_run",
        latest_activity_at: "2026-07-30T01:02:03Z",
      },
    ],
    metrics: {
      success_rate: 0.875,
      average_active_duration_ms: 4200,
      waiting_approvals: 3,
      tool_failure_rate: 0.125,
      retry_count: 7,
      quality_distribution: [
        { label: "complete", count: 5 },
        { label: "partial", count: 2 },
      ],
      token_usage: {
        input_tokens: 111,
        output_tokens: 222,
        total_tokens: 333,
      },
    },
  });

  const summary = summarizeDashboardSnapshot(snapshot);

  assert.equal(snapshot.recentRuns.length, 1);
  assert.equal(summary.windowLabel, "2026-07-01 -> 2026-07-30");
  assert.equal(summary.metricCards[0].label, "Recent runs");
  assert.equal(summary.metricCards[0].value, "1");
  assert.equal(summary.recentRuns[0].statusLabel, "Completed");
  assert.equal(summary.recentRuns[0].activityLabel, "2026-07-30T01:02:03Z");
  assert.equal(summary.qualityBuckets[0].count, 5);
  assert.equal(summary.tokenSummary[2].value, "333");
});
