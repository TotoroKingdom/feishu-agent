import assert from "node:assert/strict";
import test from "node:test";

import { buildConfigurationConfirmation } from "../lib/configuration.js";

test("buildConfigurationConfirmation redacts secrets in before and after snapshots", async () => {
  const review = await buildConfigurationConfirmation({
    kind: "project",
    before: {
      name: "Project Alpha",
      defaultPeriodRule: { type: "previous_calendar_week" },
      secret: "old-secret",
      revision: 2,
    },
    after: {
      name: "Project Beta",
      defaultPeriodRule: { type: "previous_calendar_week" },
      secret: "new-secret",
      revision: 3,
    },
  });

  assert.equal(review.kind, "project");
  assert.equal(review.canSubmit, true);
  assert.equal(review.requiresFreshRevision, true);
  assert.equal(review.before.secret, "••••");
  assert.equal(review.after.secret, "••••");
  assert.match(review.requestHash, /^[0-9a-f]{64}$/);
});

test("buildConfigurationConfirmation produces a stable request hash for repeated confirmation", async () => {
  const first = await buildConfigurationConfirmation({
    kind: "repository",
    before: {
      externalId: "acme/frontend",
      revision: 4,
    },
    after: {
      externalId: "acme/frontend",
      revision: 4,
      enabled: true,
    },
  });
  const second = await buildConfigurationConfirmation({
    kind: "repository",
    before: {
      externalId: "acme/frontend",
      revision: 4,
    },
    after: {
      externalId: "acme/frontend",
      revision: 4,
      enabled: true,
    },
  });

  assert.equal(first.requestHash, second.requestHash);
  assert.deepEqual(first.changeSummary, second.changeSummary);
});
