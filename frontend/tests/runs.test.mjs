import assert from "node:assert/strict";
import test from "node:test";

import {
  buildRunListSearchParams,
  normalizeRunListPage,
  summarizeRunListRow,
} from "../lib/admin-observability.js";

test("run list helpers encode filters and preserve cursor pagination", () => {
  const query = buildRunListSearchParams({
    status: "waiting",
    createdFrom: "2026-07-01",
    createdTo: "2026-07-30",
    requesterId: "alice",
    periodStart: "2026-07-20",
    periodEnd: "2026-07-27",
    hasHumanInput: true,
    hasRetry: false,
    hasPartialFailure: true,
    cursor: "20",
    limit: 20,
  });

  assert.equal(
    query,
    "status=waiting&created_from=2026-07-01&created_to=2026-07-30&requester_id=alice&period_start=2026-07-20&period_end=2026-07-27&has_human_input=true&has_retry=false&has_partial_failure=true&cursor=20&limit=20",
  );

  const page = normalizeRunListPage({
    data: [
      {
        run_id: "run-1",
        project_id: "project-1",
        period_key: "2026-W30",
        status: "waiting",
        current_stage: "waiting_generation_approval",
        current_node: "wait_generation_confirmation",
        requester_id: "alice",
        latest_activity_at: "2026-07-30T01:02:03Z",
        has_retry: true,
        has_partial_failure: false,
      },
    ],
    page: {
      next_cursor: "20",
      has_more: true,
      limit: 20,
    },
    meta: {
      request_id: "req-1",
    },
  });

  assert.equal(page.items.length, 1);
  assert.equal(page.nextCursor, "20");
  assert.equal(page.hasMore, true);
  assert.equal(page.requestId, "req-1");

  const summary = summarizeRunListRow(page.items[0]);
  assert.equal(summary.statusLabel, "Waiting");
  assert.equal(summary.activityLabel, "2026-07-30T01:02:03Z");
  assert.equal(summary.badges.includes("Retry"), true);
});
