import assert from "node:assert/strict";
import test from "node:test";

import { summarizeRepositoryConfiguration } from "../lib/configuration.js";

const repositories = [
  {
    id: "repo-1",
    owner: "acme",
    repo: "frontend",
    repository_type: "github",
    external_id: "acme/frontend",
    provider: "github",
    weight: 90,
    enabled: true,
    default_branch: "main",
    last_connectivity_status: "ok",
    last_connectivity_at: "2026-07-30T01:00:00Z",
    revision: 3,
    updated_at: "2026-07-30T01:00:00Z",
  },
  {
    id: "repo-2",
    owner: "acme",
    repo: "backend",
    repository_type: "github",
    external_id: "acme/backend",
    provider: "github",
    weight: 80,
    enabled: false,
    default_branch: "main",
    last_connectivity_status: "failed",
    last_connectivity_at: "2026-07-30T01:10:00Z",
    revision: 4,
    updated_at: "2026-07-30T01:10:00Z",
  },
];

test("summarizeRepositoryConfiguration keeps capacity within five repositories", () => {
  const summary = summarizeRepositoryConfiguration(repositories);

  assert.equal(summary.count, 2);
  assert.equal(summary.capacityStatus, "ready");
  assert.equal(summary.remainingSlots, 3);
  assert.equal(summary.enabledCount, 1);
  assert.equal(summary.connectivityCounts.ok, 1);
  assert.equal(summary.connectivityCounts.failed, 1);
  assert.equal(summary.rows[0].externalId, "acme/frontend");
});

test("summarizeRepositoryConfiguration flags more than five repositories", () => {
  const summary = summarizeRepositoryConfiguration([
    ...repositories,
    { ...repositories[0], id: "repo-3", external_id: "acme/docs", repo: "docs" },
    { ...repositories[0], id: "repo-4", external_id: "acme/design", repo: "design" },
    { ...repositories[0], id: "repo-5", external_id: "acme/app", repo: "app" },
    { ...repositories[0], id: "repo-6", external_id: "acme/site", repo: "site" },
  ]);

  assert.equal(summary.count, 6);
  assert.equal(summary.capacityStatus, "over_limit");
  assert.match(summary.capacityMessage, /最多 5 个/);
});
